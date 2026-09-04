"""Tests for the shared BM25 tokenizer."""

from app.rag.tokenize import STOPWORDS, tokenize


def test_stems_morphological_variants_together():
    """The bug this tokenizer exists to fix: 'engineering' must match 'engineer'."""
    assert tokenize("engineering") == tokenize("engineer") == tokenize("engineers")


def test_possessive_matches_bare_name():
    assert tokenize("David's") == tokenize("David")


def test_strips_punctuation():
    assert tokenize("(BOMs).") == tokenize("BOM")


def test_drops_stopwords():
    tokens = tokenize("the experience of a data scientist")
    assert "the" not in tokens
    assert "of" not in tokens
    assert "a" not in tokens
    # Content words survive, in order.
    assert tokens == tokenize("experience data scientist")


def test_keeps_negations():
    """'not' carries meaning in a resume Q&A corpus and must survive."""
    assert "not" in tokenize("I have not done fine-tuning")


def test_keeps_single_character_tokens():
    """R is a language on this resume; dropping short tokens would hide it."""
    assert tokenize("R") == ["r"]
    assert "r" in tokenize("Leverage R to identify hazardous materials")


def test_splits_hyphenated_model_names():
    """A query for 'mpnet' should reach a document saying 'all-mpnet-base-v2'."""
    tokens = tokenize("all-mpnet-base-v2")
    assert "mpnet" in tokens
    assert "v2" in tokens


def test_trailing_symbols_dropped_so_security_plus_is_reachable():
    assert tokenize("Security+") == tokenize("security")


def test_keeps_internal_dots():
    assert tokenize("node.js") == tokenize("Node.js")


def test_is_case_insensitive():
    assert tokenize("FastAPI FAISS") == tokenize("fastapi faiss")


def test_returns_empty_for_stopwords_only():
    assert tokenize("the and of with") == []


def test_stopwords_exclude_meaningful_technical_terms():
    for term in ("r", "ai", "ml", "no", "not"):
        assert term not in STOPWORDS
