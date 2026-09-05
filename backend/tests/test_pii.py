"""Regression guard: no contact PII may reach the retrieval index.

The chatbot is a public endpoint that reads indexed text back to anyone who
asks for it. A home address or phone number that lands in the corpus is
therefore disclosed on request. These tests fail the build if that ever happens
again, which is the durable fix — the redaction in build_index.py is only the
mechanism.
"""

import json
import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

sys.path.insert(0, str(BACKEND_ROOT / "scripts"))
from build_index import _redact_pii  # noqa: E402  (needs the sys.path line above)

# Deliberately broader than the redaction patterns in build_index.py, and the
# asymmetry is the point. The redactor rewrites the corpus silently, so it is
# precise: a false positive there deletes real content and nobody finds out.
# This is a detector — its only power is to fail a build — so a false positive
# costs one human glance. It therefore casts the wide net, including bare
# 10-digit runs and punctuation-free international forms that the redactor
# deliberately leaves alone.
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
STREET_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+)*?\s+"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Blvd|Boulevard|"
    r"Way|Cir|Circle|Pl|Place|Ter|Terrace|Pkwy|Parkway)\.?\s*,",
    re.IGNORECASE,
)

# Every document load_documents() indexes must be scanned. The MDX write-ups
# were missing here even though build_index.py feeds them to the same index.
SOURCE_DOCS = [
    REPO_ROOT / "docs" / "resume.txt",
    REPO_ROOT / "docs" / "chatbot-questions.md",
    *sorted((REPO_ROOT / "frontend" / "content" / "projects").glob("*.mdx")),
]


def _chunk_texts() -> list[str]:
    path = BACKEND_ROOT / "indexes" / "chunks.json"
    return [c["text"] for c in json.loads(path.read_text(encoding="utf-8"))]


def test_committed_index_has_no_phone_numbers():
    offenders = [t for t in _chunk_texts() if PHONE_RE.search(t)]
    assert not offenders, f"Phone number found in {len(offenders)} indexed chunk(s)"


def test_committed_index_has_no_street_address():
    offenders = [t for t in _chunk_texts() if STREET_RE.search(t)]
    assert not offenders, f"Street address found in {len(offenders)} indexed chunk(s)"


@pytest.mark.parametrize("path", SOURCE_DOCS, ids=lambda p: p.name)
def test_source_documents_have_no_contact_pii(path: Path):
    """Redaction is a backstop; the sources should be clean to begin with."""
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    text = path.read_text(encoding="utf-8")
    assert not PHONE_RE.search(text), f"Phone number in {path.name}"
    assert not STREET_RE.search(text), f"Street address in {path.name}"


def test_redactor_strips_phone_and_address():
    text = "David West\n6482 Misty Ct, Waterford, MI 48327  ●  (586) 549-3786  ●  a@b.com"
    result = _redact_pii(text)
    assert "Misty Ct" not in result
    assert "549-3786" not in result
    assert "David West" in result
    assert "a@b.com" in result, "email is a published contact method and should survive"


@pytest.mark.parametrize(
    "text",
    [
        "Employed 2018-2021 at 40 Hrs/Week",
        "GPA: 3.57",
        "Promoted from GS-1515-07 to GS-1515-09",
        "The corpus holds roughly 7,300 chunks",
        "Version 1.2.3 released 2025-01-15",
    ],
)
def test_redactor_leaves_ordinary_resume_text_alone(text: str):
    """Guards against a redaction pattern that eats dates, grades, or versions."""
    assert _redact_pii(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "5865493786",
        "(586)5493786",
        "+15865493786",
        "586 549 3786",
        "(586) 549-3786",
        "586-549-3786",
        "+1 586.549.3786",
    ],
)
def test_guard_catches_every_phone_format_including_bare_digits(text: str):
    """The detector is the wide net.

    It must match formats the redactor deliberately skips, because for those the
    build failing *is* the fix: the source document gets corrected rather than
    the corpus silently rewritten.
    """
    assert PHONE_RE.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "Processed 4500000000 records",
        "Latency dropped 200 300 4000 ms",
        "Serial 1234567890123",
        "Handled 12,500,000 rows",
    ],
)
def test_redactor_does_not_eat_ordinary_numbers(text: str):
    """The redactor mutates the corpus silently, so it must not guess.

    A bare or space-separated digit run is indistinguishable from a metric, an
    identifier, or a quantity. Redacting those degrades retrieval with no signal
    that anything was lost.
    """
    assert _redact_pii(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "Phone: 586 549 3786",
        "cell 5865493786",
        "Tel. +1 586 549 3786",
    ],
)
def test_redactor_strips_ambiguous_formats_when_labelled(text: str):
    """A nearby label resolves the ambiguity, so the redactor can act safely."""
    assert "[redacted]" in _redact_pii(text)
