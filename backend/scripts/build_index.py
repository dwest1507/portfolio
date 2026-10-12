"""
Pre-processing script: chunk documents, build FAISS + BM25 indexes.

Run once before deploying:
    python scripts/build_index.py

Reads:
  - ../../docs/resume.txt                   David's resume
  - ../../docs/chatbot-questions.md         The question document
  - ../../frontend/content/projects/*.mdx   Project write-ups
  - ../../frontend/data/projects.ts         Project titles, which head their sections

Each source is cut into Chunks along its own structure (see chunk_document): one per
question-and-answer pair, one per project section headed `<project title> — <section>`,
and one per resume section or role headed `<employer> — <role>`. A unit over CHUNK_SIZE
is split at line and sentence boundaries with its heading repeated on every piece.

Writes to indexes/:
  - chunks.json     List of {"text": str, "source": str}
  - faiss.index     FAISS inner-product index (cosine sim on normalised vecs)
  - onnx_embeddings.npy  The same embeddings computed on ONNX Runtime, for the
                         Candidate Arms (normalised float32, one row per chunk)
  - bm25.pkl        BM25Okapi index
"""

import json
import pickle
import re
import sys
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.rag.onnx_models import OnnxEmbedder
from app.rag.tokenize import tokenize

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent
INDEXES_DIR = BACKEND_ROOT / "indexes"
RESUME_PATH = REPO_ROOT / "docs" / "resume.txt"
QA_PATH = REPO_ROOT / "docs" / "chatbot-questions.md"
MDX_DIR = REPO_ROOT / "frontend" / "content" / "projects"
PROJECTS_DATA_PATH = REPO_ROOT / "frontend" / "data" / "projects.ts"

CHUNK_SIZE = 1000  # characters (~250-300 tokens); an over-long unit is split, see _headed


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

# The resume is a public document, but the chatbot is a retrieval system that
# will happily read any indexed line back to an anonymous visitor who asks for
# it. Contact details that are fine on a PDF sent to a specific recruiter are
# not fine coming out of a public endpoint on request, so they are stripped
# before anything reaches the index. This is a backstop: the source documents
# should not contain them either.

# Redaction is deliberately PRECISE, not permissive. It rewrites the corpus
# silently, so a false positive destroys real content (a metric, an ID, a
# quantity) with nobody the wiser, and degrades the retrieval quality that
# eval/ exists to measure. The broad net lives in tests/test_pii.py instead:
# that one only has to fail a build, so a false positive there costs one human
# glance rather than a hole in the index.
#
# Concretely: a bare 10-digit run like "5865550147" is NOT redacted here,
# because it is indistinguishable from an ordinary number. test_pii.py does
# match it, so it fails the build and the source document gets fixed — which is
# the stated order of operations anyway ("the sources should be clean to begin
# with").

# Separators that actually mark a phone number rather than a numeric coincidence.
_PHONE_PUNCT = r"[.-]"

_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Phone numbers written with unambiguous phone punctuation:
    #   (586) 555-0147 | 586-555-0147 | +1 586.555.0147 | (586)555-0147
    # A parenthesized area code, or dot/dash separators, marks intent. Bare or
    # space-only separated digit runs are left to the test guard (see above).
    (
        re.compile(
            r"(?<!\d)(?:\+?1[\s.-]?)?"
            r"(?:\(\d{3}\)\s*|\d{3}" + _PHONE_PUNCT + r")"
            r"\d{3}" + _PHONE_PUNCT + r"\d{4}(?!\d)"
        ),
        "[redacted]",
    ),
    # Phone numbers with ambiguous separators (spaces, or none at all), but
    # carrying an explicit label that resolves the ambiguity:
    #   "Phone: 586 555 0147" | "cell 5865550147" | "Tel. +1 586 555 0147"
    (
        re.compile(
            r"(?i:\b(?:phone|tel|telephone|mobile|cell|fax|contact)\b\.?\s*:?\s*)"
            r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
        ),
        "[redacted]",
    ),
    # Street address followed by a city/state/ZIP, e.g.
    # "742 Evergreen Ter, Springfield, IL 62704"
    (
        re.compile(
            r"\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+)*?\s+"
            r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Blvd|Boulevard|"
            r"Way|Cir|Circle|Pl|Place|Ter|Terrace|Pkwy|Parkway)\.?"
            r"(?:\s*,\s*[A-Za-z .'-]+)?\s*,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b",
            re.IGNORECASE,
        ),
        "[redacted]",
    ),
]


def _redact_pii(text: str) -> str:
    """Strip home address and phone numbers before indexing."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


def _strip_mdx(text: str) -> str:
    """Remove markdown/MDX syntax, keeping plain prose."""
    # Remove fenced code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove markdown links  [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove bare URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove markdown images
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Remove heading markers but keep text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Structure-aware chunking
# ---------------------------------------------------------------------------

# A bold line on its own is a question in docs/chatbot-questions.md. Everything up to the
# next question, section heading or rule is its answer.
_QUESTION_LINE = re.compile(r"^\*\*(?P<question>[^*]+)\*\*\s*$", re.MULTILINE)
_ANSWER_END = re.compile(r"^(?:---+\s*|#{1,6}\s.*)$", re.MULTILINE)


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _lines(text: str) -> list[str]:
    """Non-blank lines, stripped."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _headed(heading: str, lines: list[str], source: str) -> list[dict]:
    """One Chunk of `heading` over `lines`, or several when that exceeds CHUNK_SIZE.

    An over-long unit is split at line and then sentence boundaries, never inside a
    sentence, and every piece starts with the heading so it still says what it is about.
    A single sentence longer than the limit is kept whole rather than cut.
    """
    budget = CHUNK_SIZE - len(heading) - 1
    # (separator from the previous segment, segment)
    segments: list[tuple[str, str]] = []
    for line in lines:
        parts = [line] if len(line) <= budget else _SENTENCE_END.split(line)
        segments.extend(("\n" if i == 0 else " ", part) for i, part in enumerate(parts))

    pieces: list[str] = []
    current = ""
    for separator, segment in segments:
        if current and len(current) + len(separator) + len(segment) > budget:
            pieces.append(current)
            current = ""
        current = current + separator + segment if current else segment
    if current:
        pieces.append(current)
    return [{"text": f"{heading}\n{piece}", "source": source} for piece in pieces]


def _chunk_questions(text: str, source: str) -> list[dict]:
    questions = list(_QUESTION_LINE.finditer(text))
    chunks = []
    for match, following in zip(questions, questions[1:] + [None]):
        body = text[match.end() : following.start() if following else len(text)]
        end = _ANSWER_END.search(body)
        answer = _lines(_strip_mdx(body[: end.start()] if end else body))
        # A question not yet answered is not a pair. Indexed alone it would match its own
        # paraphrases and hand the model a Chunk with nothing in it.
        if answer:
            chunks.extend(_headed(match["question"].strip(), answer, source))
    return chunks


_SECTION_HEADING = re.compile(r"^##\s+(?P<heading>.+?)\s*$", re.MULTILINE)


def _chunk_sections(text: str, source: str, title: str) -> list[dict]:
    sections = list(_SECTION_HEADING.finditer(text))
    chunks = []
    for match, following in zip(sections, sections[1:] + [None]):
        body = _lines(_strip_mdx(text[match.end() : following.start() if following else None]))
        chunks.extend(_headed(f"{title} — {match['heading']}", body, source))
    return chunks


# The resume is plain text: a section starts at an all-capitals line, and a role starts at
# the line before its date range ("May 2020 – January 2021"), with the employer after it.
_RESUME_SECTION = re.compile(r"^[A-Z][A-Z /&]*[A-Z]$")
_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
)
_ROLE_DATES = re.compile(rf"^{_MONTH} \d{{4}}\s*[–-]\s*(?:Present|{_MONTH} \d{{4}})")
_EXPERIENCE = "EXPERIENCE"


def _chunk_roles(lines: list[str], source: str) -> list[dict]:
    starts = [i for i, line in enumerate(lines) if _ROLE_DATES.match(line)]
    if not starts or starts[0] != 1:
        raise ValueError(
            f"{source}: {_EXPERIENCE} must be a list of roles, each title, dates, employer"
        )
    chunks = []
    for dates, following in zip(starts, starts[1:] + [len(lines) + 1]):
        role, employer = lines[dates - 1], lines[dates + 1]
        body = [lines[dates], *lines[dates + 2 : following - 1]]
        chunks.extend(_headed(f"{employer} — {role}", body, source))
    return chunks


def _chunk_resume(text: str, source: str) -> list[dict]:
    sections: list[tuple[str, list[str]]] = []
    for line in (line.strip() for line in text.splitlines()):
        if _RESUME_SECTION.match(line):
            sections.append((line, []))
        elif line and sections:
            sections[-1][1].append(line)

    chunks = []
    for heading, lines in sections:
        if heading == _EXPERIENCE:
            chunks.extend(_chunk_roles(lines, source))
        elif lines:
            chunks.extend(_headed(f"Resume — {heading.title()}", lines, source))
    return chunks


def chunk_document(text: str, source: str, title: str | None = None) -> list[dict]:
    """Cut one Corpus document into Chunks along its own structure.

    The single chunking entry point: `source` names the document's kind, and each kind
    has one rule. A project write-up also needs its `title`, which heads every section.
    PII redaction has already run on `text` (see load_documents).

    A document its rule finds no structure in is an error, not an empty contribution: a
    formatting change must fail the build rather than quietly drop a source.
    """
    if source == "qa":
        chunks = _chunk_questions(text, source)
    elif source == "resume":
        chunks = _chunk_resume(text, source)
    elif source.startswith("project:"):
        if not title:
            raise ValueError(f"{source} needs the project's title to head its sections")
        chunks = _chunk_sections(text, source, title)
    else:
        raise ValueError(f"No chunking rule for source {source!r}")
    if not chunks:
        raise ValueError(f"{source}: found no structure to chunk along")
    return chunks


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------


# A project write-up's title lives with the rest of its card data in the frontend, not
# in the MDX, so it is read from there rather than repeated.
_PROJECT_TITLE = re.compile(r"slug:\s*'(?P<slug>[^']+)',\s*title:\s*'(?P<title>[^']+)'")


def project_titles() -> dict[str, str]:
    """Each project's display title, keyed by the slug its MDX file is named after."""
    data = PROJECTS_DATA_PATH.read_text(encoding="utf-8")
    return {m["slug"]: m["title"] for m in _PROJECT_TITLE.finditer(data)}


def load_documents() -> list[dict]:
    """Every Corpus source, PII-redacted but otherwise raw: its structure is what chunking
    cuts along, so markup is stripped per Chunk rather than here."""
    docs: list[dict] = []

    # Resume
    if not RESUME_PATH.exists():
        print(f"WARNING: Resume not found at {RESUME_PATH}", file=sys.stderr)
    else:
        text = _redact_pii(RESUME_PATH.read_text(encoding="utf-8"))
        docs.append({"text": text, "source": "resume"})
        print(f"  Loaded resume ({len(text)} chars)")

    # Chatbot Q&A
    if not QA_PATH.exists():
        print(f"WARNING: Q&A file not found at {QA_PATH}", file=sys.stderr)
    else:
        text = _redact_pii(QA_PATH.read_text(encoding="utf-8"))
        docs.append({"text": text, "source": "qa"})
        print(f"  Loaded chatbot-questions.md ({len(text)} chars)")

    # MDX project write-ups
    mdx_files = sorted(MDX_DIR.glob("*.mdx"))
    if not mdx_files:
        print(f"WARNING: No MDX files found in {MDX_DIR}", file=sys.stderr)
    titles = project_titles()
    for mdx_path in mdx_files:
        text = _redact_pii(mdx_path.read_text(encoding="utf-8"))
        slug = mdx_path.stem
        if slug not in titles:
            raise ValueError(f"{mdx_path.name} has no project in {PROJECTS_DATA_PATH.name}")
        docs.append({"text": text, "source": f"project:{slug}", "title": titles[slug]})
        print(f"  Loaded {slug} ({len(text)} chars)")

    return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    INDEXES_DIR.mkdir(exist_ok=True)

    print("Loading documents...")
    docs = load_documents()

    print("\nChunking documents...")
    all_chunks: list[dict] = []
    for doc in docs:
        chunks = chunk_document(doc["text"], doc["source"], doc.get("title"))
        all_chunks.extend(chunks)
        print(f"  {doc['source']}: {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")
    lengths = [len(c["text"]) for c in all_chunks]
    print(
        f"  Avg: {sum(lengths) / len(lengths):.0f} chars, Min: {min(lengths)}, Max: {max(lengths)}"
    )

    # Save chunks
    with open(INDEXES_DIR / "chunks.json", "w") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print("\nSaved chunks.json")

    # Embed with sentence-transformers
    print("\nGenerating embeddings (sentence-transformers/all-mpnet-base-v2)...")
    embedder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    embeddings = embeddings.astype(np.float32)

    # Build FAISS index (inner product = cosine sim on normalised vecs)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, str(INDEXES_DIR / "faiss.index"))
    print(f"Saved faiss.index ({index.ntotal} vectors, dim={dim})")

    # The same model on ONNX Runtime, for the Candidate Arms (ADR-0009). Embedded here, not
    # at query time, so their load band counts loading the model and not embedding the
    # Corpus — the cost a production image would actually pay.
    print("\nGenerating embeddings (all-mpnet-base-v2 on ONNX Runtime)...")
    onnx_embeddings = OnnxEmbedder().encode(texts)
    np.save(INDEXES_DIR / "onnx_embeddings.npy", onnx_embeddings)
    print(f"Saved onnx_embeddings.npy ({onnx_embeddings.shape[0]} vectors)")

    # Build BM25 index
    tokenized_corpus = [tokenize(c["text"]) for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(INDEXES_DIR / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
    print("Saved bm25.pkl")

    print("\nDone. Ready to start the FastAPI server.")


if __name__ == "__main__":
    main()
