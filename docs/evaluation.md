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

The `dense` arm has no threshold entry, because it has never been measured (see
below). `--check` names any ungated arm explicitly, and a run in which *nothing*
was gated — `--check --arms dense` — is a failure rather than a pass.

Useful flags:

```bash
uv run python eval/run_eval.py --arms hybrid rerank   # subset
uv run python eval/run_eval.py --failures             # list the questions that missed
uv run python eval/run_eval.py --json results.json    # machine-readable
uv run python eval/run_eval.py --check                # exit 1 below thresholds
```

## Results

### BM25 tokenizer change

Both the index builder and the query path previously tokenized with
`text.lower().split()`. That never matched "engineering" against "engineer",
never matched "David's" against "David", left punctuation attached to terms, and
scored stopwords as if they carried meaning. Replacing it with a shared
stopword-filtered Snowball-stemmed tokenizer, measured on the BM25 arm:

| Tokenizer | recall@5 | hit@5 | MRR | nDCG@5 |
|-----------|---------:|------:|----:|-------:|
| `.lower().split()` | 0.595 | 0.836 | 0.644 | 0.549 |
| stopwords + Snowball stemming | **0.711** | **0.909** | **0.839** | **0.723** |
| change | +0.116 | +0.073 | **+0.196** | +0.174 |

A 30% relative improvement in MRR from the tokenizer alone — the largest
single-change gain measured so far, and it costs nothing at query time.

### Arm comparison

The BM25 baseline is recorded below. The dense, hybrid, and rerank rows are
produced by the CI `Retrieval eval` job, which has the model weights available;
fill them in here from that run's output.

| Arm | recall@5 | hit@5 | MRR | nDCG@5 |
|-----|---------:|------:|----:|-------:|
| `bm25` | 0.711 | 0.909 | 0.839 | 0.723 |
| `dense` | — | — | — | — |
| `hybrid` | — | — | — | — |
| `rerank` | — | — | — | — |

The five questions BM25 alone misses are all semantic paraphrases, which is
exactly the gap dense retrieval is supposed to close:

- "What is David's current job title?" (corpus says *Data Scientist, Lead*)
- "What did David study in college?" (corpus says *Major: Biochemistry*)
- "Does David have a computer science degree?"
- "What cloud providers has David used?" (corpus says *cloud platforms*)
- "Has David built models that predict equipment failure?" (corpus says
  *predicts when parts will fail*)

## CI gate

`.github/workflows/backend-ci.yml` runs `scripts/backend-eval.sh` on every
backend change. The job fails if any gated arm falls below the floors in
`eval/run_eval.py`, so a change that degrades retrieval cannot merge silently.

Floors are currently set to the measured BM25 baseline rounded down (hit@5 ≥
0.85, MRR ≥ 0.75). BM25 alone is the weakest arm, so any configuration scoring
below it is a real regression. Raise the floors once the full four-arm run is
recorded above.

## Scope and honesty about it

The corpus is 42 chunks. Retrieving 10 candidates means touching roughly a
quarter of it, so this is not a hard retrieval problem, and the absolute numbers
should be read with that in mind. The pipeline is built at production
complexity — hybrid retrieval, cross-encoder re-ranking, a measured regression
gate — deliberately, to demonstrate the pattern on a corpus small enough to
label exhaustively by hand.

## Not yet measured

Retrieval quality is only half of a RAG system's behaviour. Still open:
generation faithfulness (does the answer stay inside the retrieved context?),
refusal behaviour on out-of-scope questions, and adversarial/prompt-injection
robustness. See the portfolio improvement issue for the plan.
