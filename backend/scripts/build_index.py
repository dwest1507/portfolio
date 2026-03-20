"""
Pre-processing script: chunk documents, build FAISS + BM25 indexes.

Run once before deploying:
    python scripts/build_index.py

Reads:
  - ../../docs/resume.txt         David's resume
  - ../../frontend/content/projects/*.mdx   Project write-ups

Writes to indexes/:
  - chunks.json     List of {"text": str, "source": str}
  - faiss.index     FAISS inner-product index (cosine sim on normalised vecs)
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent
INDEXES_DIR = BACKEND_ROOT / "indexes"
RESUME_PATH = REPO_ROOT / "docs" / "resume.txt"
MDX_DIR = REPO_ROOT / "frontend" / "content" / "projects"

CHUNK_SIZE = 1000   # characters (~250-300 tokens)
CHUNK_OVERLAP = 100


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


def _chunk_text(text: str, source: str) -> list[dict]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[dict] = []
    current = ""

    for para in paragraphs:
        # If adding this paragraph stays within limit, accumulate
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            # Flush current buffer (if any)
            if current:
                chunks.append({"text": current, "source": source})
            # If the paragraph itself is too long, split by sentence
            if len(para) > CHUNK_SIZE:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub_current = ""
                for sent in sentences:
                    candidate = (sub_current + " " + sent).strip() if sub_current else sent
                    if len(candidate) <= CHUNK_SIZE:
                        sub_current = candidate
                    else:
                        if sub_current:
                            chunks.append({"text": sub_current, "source": source})
                        sub_current = sent
                if sub_current:
                    chunks.append({"text": sub_current, "source": source})
                current = ""
            else:
                current = para

    if current:
        chunks.append({"text": current, "source": source})

    # Add overlap: prepend tail of previous chunk to next chunk
    overlapped: list[dict] = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            prev_text = chunks[i - 1]["text"]
            overlap_text = prev_text[-CHUNK_OVERLAP:] if len(prev_text) > CHUNK_OVERLAP else prev_text
            # Only add overlap if it doesn't push us way over the limit
            merged = (overlap_text + " " + chunk["text"]).strip()
            if len(merged) <= CHUNK_SIZE * 1.3:
                overlapped.append({"text": merged, "source": chunk["source"]})
                continue
        overlapped.append(chunk)

    return overlapped


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_documents() -> list[dict]:
    docs: list[dict] = []

    # Resume
    if not RESUME_PATH.exists():
        print(f"WARNING: Resume not found at {RESUME_PATH}", file=sys.stderr)
    else:
        text = RESUME_PATH.read_text(encoding="utf-8")
        docs.append({"text": text, "source": "resume"})
        print(f"  Loaded resume ({len(text)} chars)")

    # MDX project write-ups
    mdx_files = sorted(MDX_DIR.glob("*.mdx"))
    if not mdx_files:
        print(f"WARNING: No MDX files found in {MDX_DIR}", file=sys.stderr)
    for mdx_path in mdx_files:
        raw = mdx_path.read_text(encoding="utf-8")
        text = _strip_mdx(raw)
        slug = mdx_path.stem
        docs.append({"text": text, "source": f"project:{slug}"})
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
        chunks = _chunk_text(doc["text"], doc["source"])
        all_chunks.extend(chunks)
        print(f"  {doc['source']}: {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")
    lengths = [len(c["text"]) for c in all_chunks]
    print(f"  Avg: {sum(lengths)/len(lengths):.0f} chars, Min: {min(lengths)}, Max: {max(lengths)}")

    # Save chunks
    with open(INDEXES_DIR / "chunks.json", "w") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"\nSaved chunks.json")

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

    # Build BM25 index
    tokenized_corpus = [c["text"].lower().split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(INDEXES_DIR / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
    print(f"Saved bm25.pkl")

    print("\nDone. Ready to start the FastAPI server.")


if __name__ == "__main__":
    main()
