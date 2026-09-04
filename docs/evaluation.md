# Retrieval Evaluation

The chatbot's answers are only as good as the passages retrieved for them, so
retrieval is measured rather than assumed. This document covers what is
measured, how, and what the numbers currently say.

## Why this exists

Before this harness, the pipeline's key parameters — a 70/30 split between
semantic and keyword search, 10 candidates narrowed to 5 by a cross-encoder —
were asserted with no evidence. There was no way to answer "does the
cross-encoder stage earn its latency?" or "would dense-only be just as good?",
and no way to notice if a change to chunking quietly broke retrieval.

## Method

**Golden set** — `backend/eval/golden_set.json` holds 55 questions of the kind a
recruiter, hiring manager, or technical interviewer would actually ask, spanning
employment history, skills, projects, education, and logistics.

**Relevance labels** — each question lists `relevant_phrases`. A retrieved chunk
counts as relevant if its text contains any of them (case- and
whitespace-insensitive). Labelling by phrase rather than by chunk ID means the
golden set stays valid when the corpus is re-chunked or re-indexed, which chunk
IDs would not survive.

**Arms** — four retrieval configurations are compared on identical inputs:

| Arm | What it does |
|-----|--------------|
| `bm25` | Keyword search only. Needs no embedding model. |
| `dense` | FAISS semantic search only. |
| `hybrid` | Weighted reciprocal-rank fusion of both. |
| `rerank` | Hybrid candidates re-ordered by the cross-encoder. |

**Metrics**

- **hit@5** — did *any* relevant chunk make the top 5? This is the metric that
  decides whether the LLM can answer at all, and it is what CI gates on.
- **recall@5** — what fraction of all relevant chunks made the top 5. Reported
  for information only. It is a poor gate here: several questions have more than
  five relevant chunks, so their recall@5 is capped below 1.0 by construction.
- **MRR** — mean reciprocal rank of the first relevant chunk, truncated at the
  same cutoff as the other metrics. Captures how far up the list the good
  passage landed, which matters because the model attends unevenly across a
  long context.
- **nDCG@5** — rank-discounted gain, as a cross-check on MRR.

## Running it

```bash
make eval        # all four arms (downloads ~500MB of models on first run)
make eval-fast   # BM25 arm only — no model download, runs in seconds
```

`--top-k` moves the cutoff, and every metric follows it — `--top-k 10` reports
`hit@10`, `recall@10`, `ndcg@10` and an MRR truncated at 10. The thresholds are
calibrated at k=5, so `--check` only runs at the default cutoff and fails
loudly rather than comparing a `hit@10` against a `hit@5` floor.

The `dense` arm has no threshold entry: it is measured and reported as a
baseline, not defended as a quality bar (see the results below). `--check` names
any ungated arm explicitly, and a run in which *nothing* was gated —
`--check --arms dense` — is a failure rather than a pass.

Useful flags:

```bash
uv run python eval/run_eval.py --arms hybrid rerank   # subset
uv run python eval/run_eval.py --failures             # list the questions that missed
uv run python eval/run_eval.py --json results.json    # machine-readable
uv run python eval/run_eval.py --check                # exit 1 below thresholds
```

## Results

Measured on the current corpus (49 chunks, 55 questions) by the CI
`Retrieval eval` job at `ee674f2`.

### Arm comparison

| Arm | recall@5 | hit@5 | MRR | nDCG@5 |
|-----|---------:|------:|----:|-------:|
| `bm25` | **0.730** | **1.000** | **0.892** | **0.758** |
| `dense` | 0.571 | 0.818 | 0.688 | 0.588 |
| `hybrid` | 0.653 | 0.927 | 0.750 | 0.651 |
| `rerank` | 0.652 | 0.909 | 0.853 | 0.698 |

**Keyword search alone beats the full pipeline on every metric.** BM25 retrieves
a relevant passage for all 55 questions; the hybrid + cross-encoder pipeline
that was built on the assumption that it would do better does not.

Reading the rest of the table:

- **Dense retrieval is the weak arm here**, missing 10 questions outright.
- **Hybrid lands between its two inputs**, which is what fusion does when it
  averages a strong retriever with a weak one.
- **The cross-encoder is working.** Re-ranking lifts MRR from 0.750 to 0.853 —
  it genuinely reorders good passages upward. It cannot rescue what the
  candidate stage never gave it.

### Why lexical search wins on this corpus

Two structural reasons, both of which narrow the claim rather than support it:

1. **The corpus contains the questions.** `docs/chatbot-questions.md` is written
   as recruiter questions with answers, and the golden set asks paraphrases of
   those same questions. Lexical overlap between query and document is therefore
   unusually high. Dense retrieval earns its keep when the user's phrasing shares
   no vocabulary with the source — a case a Q&A corpus under-represents by
   construction.
2. **The labels correlate with the retriever.** Relevance is defined by exact
   phrase presence, and BM25 ranks by exact term overlap, so the labelling scheme
   and one of the arms measure something close to the same thing. Every arm was
   scored against identical labels, so the comparison is internally fair — but
   the honest claim is narrow: *on a small, keyword-dense corpus that embeds its
   own expected questions, lexical search wins here.* Not that BM25 beats dense
   retrieval in general.

### What changes as a result

The 70/30 weighting favouring dense retrieval is now a measured mistake rather
than an untested assumption. Open experiments:

- Shift `DENSE_WEIGHT` / `SPARSE_WEIGHT` toward sparse and re-measure.
- Test BM25 feeding the cross-encoder directly, dropping the dense stage — on
  this evidence that would be cheaper *and* better.
- Keep the dense arm measured regardless. The moment the corpus grows beyond
  anticipated questions, this conclusion is expected to flip.

### BM25 tokenizer change

Both the index builder and the query path previously tokenized with
`text.lower().split()`. That never matched "engineering" against "engineer",
never matched "David's" against "David", left punctuation attached to terms, and
scored stopwords as if they carried meaning. Replacing it with a shared
stopword-filtered Snowball-stemmed tokenizer, measured on the BM25 arm against
the same corpus:

| Tokenizer | recall@5 | hit@5 | MRR | nDCG@5 |
|-----------|---------:|------:|----:|-------:|
| `.lower().split()` | 0.633 | 0.945 | 0.745 | 0.618 |
| stopwords + Snowball stemming | **0.730** | **1.000** | **0.892** | **0.758** |
| change | +0.097 | +0.055 | **+0.147** | +0.140 |

Roughly 20% relative improvement in MRR from the tokenizer alone, at no query-time
cost. Index-time and query-time tokenization must match exactly, which is why
both sides import the single implementation in `app/rag/tokenize.py`.

## CI gate

`.github/workflows/backend-ci.yml` runs `scripts/backend-eval.sh` on every
backend change. The job fails if any gated arm falls below the floors in
`eval/run_eval.py`, so a change that degrades retrieval cannot merge silently.

Floors are hit@5 ≥ 0.85 and MRR ≥ 0.75, set below the measured values with
headroom for noise. `dense` is intentionally ungated — it is measured and
reported as a baseline, not defended as a quality bar.

## Scope and honesty about it

The corpus is 49 chunks. Retrieving 10 candidates touches roughly a fifth of it,
so this is not a hard retrieval problem and the absolute numbers should be read
with that in mind. The pipeline is built at production complexity — hybrid
retrieval, cross-encoder re-ranking, a measured regression gate — deliberately,
to demonstrate the pattern on a corpus small enough to label exhaustively by
hand. The eval earning its keep by contradicting the architecture is the point,
not an embarrassment to hide.

## Not yet measured

Retrieval quality is only half of a RAG system's behaviour. Still open:
generation faithfulness (does the answer stay inside the retrieved context?),
refusal behaviour on out-of-scope questions, and adversarial/prompt-injection
robustness. See the portfolio improvement issue for the plan.
