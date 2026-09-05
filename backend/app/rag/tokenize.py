"""Shared BM25 tokenizer.

The index builder and the query path MUST tokenize identically — a mismatch
silently degrades keyword recall, because a query token that was stemmed one way
can never match a document token stemmed another way. Keeping the single
implementation here is what guarantees that.

Previously both sides used ``text.lower().split()``, which meant:
  - "engineering" never matched "engineer"
  - "David's" never matched "David"
  - punctuation rode along on tokens ("(BOMs)." was one term)
  - high-frequency words ("the", "and", "with") were scored as if meaningful

Single-character tokens are deliberately KEPT: "R" is a language on this resume
and dropping short tokens would make it unsearchable.
"""

import re

import snowballstemmer

# Conservative English stopword list. Deliberately excludes words that carry
# meaning in a technical resume (e.g. "it" is dropped but "no"/"not" are kept so
# negations survive).
_STOPWORD_SOURCE = """
    a about above after again against all am an and any are as at
    be because been before being below between both but by
    can did do does doing down during
    each few for from further
    had has have having he her here hers herself him himself his how
    i if in into is it its itself
    just me more most my myself
    of off on once only or other our ours ourselves out over own
    same she should so some such
    than that the their theirs them themselves then there these they this those through to too
    under until up
    very was we were what when where which while who whom why will with
    you your yours yourself yourselves
"""

STOPWORDS: frozenset[str] = frozenset(_STOPWORD_SOURCE.split())

# Alphanumeric runs, allowing internal dots and apostrophes so "node.js" and
# "david's" survive as single tokens. Hyphens deliberately split
# ("all-mpnet-base-v2" -> all/mpnet/base/v2) so a query for "mpnet" still hits,
# and trailing symbols are dropped so "Security+" indexes as "security" and is
# reachable from a query that just says "security".
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.'][a-z0-9]+)*")

_stemmer = snowballstemmer.stemmer("english")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-word characters, drop stopwords, then stem.

    Used for both corpus indexing and query analysis so the two always agree.
    """
    words = _TOKEN_RE.findall(text.lower())
    kept = [w for w in words if w not in STOPWORDS]
    return _stemmer.stemWords(kept)
