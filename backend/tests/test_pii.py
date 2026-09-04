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
from build_index import _redact_pii

# Deliberately broader than the redaction patterns: this is a detector, not a
# sanitizer, and it should catch formats the sanitizer might have missed.
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
STREET_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+)*?\s+"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Ct|Court|Blvd|Boulevard|"
    r"Way|Cir|Circle|Pl|Place|Ter|Terrace|Pkwy|Parkway)\.?\s*,",
    re.IGNORECASE,
)

SOURCE_DOCS = [
    REPO_ROOT / "docs" / "resume.txt",
    REPO_ROOT / "docs" / "chatbot-questions.md",
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
