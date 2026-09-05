# Retrieval Evaluation

The chatbot's answers are only as good as the passages retrieved for them, so retrieval is
measured rather than assumed. This is the engineer-facing reference: how the harness works,
how to run it, and what it has caught.

The recruiter-facing write-up is the [portfolio project page](../frontend/content/projects/portfolio.mdx),
rendered at `/projects/portfolio`. It publishes the same numbers from the same source. If
the two ever disagree, one of them was edited by hand and that is the bug.

## Why this exists

The pipeline's key parameters — a weighted split between semantic and keyword search, ten
candidates narrowed to five by a cross-encoder — were asserted with no evidence. There was
no way to answer "does the cross-encoder stage earn its latency?" or "would dense-only be
just as good?", and no way to notice if a change to chunking quietly broke retrieval.

## Method

**Golden set** — `backend/eval/golden_set.json` holds questions of the kind a recruiter,
hiring manager, or technical interviewer would actually ask, spanning employment history,
skills, projects, education, and logistics.

**Relevance labels** — each question lists `relevant_phrases`. A retrieved chunk counts as
relevant if its text contains any of them (case- and whitespace-insensitive). Labelling by
phrase rather than by chunk ID means the golden set stays valid when the corpus is
re-chunked or re-indexed, which chunk IDs would not survive.

**Arms** — each arm is one retrieval configuration. Arms are defined in
`backend/eval/publish.py` (`ARM_SPECS`), which owns their identity, both registers of
description, and the `shipped` flag marking the one arm that mirrors what
`RAGPipeline.retrieve` actually runs in production. Their implementations live in
`_retrievers()` in `run_eval.py`, and `retrievers_for_arms()` refuses a run where the two
sides disagree — a published arm nothing can run, or a runnable arm nothing describes.

The arm set is not fixed. Adding or retiring one is a single edit in `ARM_SPECS`; the
published table, the markdown block below, and the project page all follow, and nothing
downstream may assume a particular arm exists. Retiring an arm from *production* is a
different act from retiring it from the harness, and the two are deliberately decoupled:
every arm this project has ever shipped is still measured on every run, so a conclusion
that flips can flip back on evidence rather than on a rewrite.

**Splits** — the golden set is partitioned into a `dev` portion (33 questions) and a
`holdout` portion (22). Parameters, weights and stage choices are decided against `dev`.
`holdout` is what `--publish` reports, so no number on the public page is the score of a
configuration that was chosen using those same questions. `--split` selects the portion.

Assignment is deterministic rather than hand-picked — cases sorted by
`sha256(salt + ":" + id)`, the first 40% held out — and *recorded* in `golden_set.json`
rather than recomputed at run time, because a frozen split is the entire point: a rule
evaluated at run time would silently reshuffle every case the day a question is added.
Recording it also makes it editable by hand, so `test_the_recorded_split_matches_the_documented_rule`
recomputes the rule and fails if a question was quietly moved across the line.

The trade is sample size. 22 questions move hit@5 in steps of about 0.045, so the
published numbers are coarser than a run over all 55 would be. That is the price of them
measuring something rather than scoring the winner of their own selection.

**Metrics**

- **hit@5** — did *any* relevant chunk make the top 5? This decides whether the LLM can
  answer at all, so it is what CI gates on and what the published verdict is decided on.
- **recall@5** — what fraction of all relevant chunks made the top 5. Reported for
  information only. It is a poor gate here: several questions have more than five relevant
  chunks, so their recall@5 is capped below 1.0 by construction.
- **MRR** — mean reciprocal rank of the first relevant chunk, truncated at the same cutoff
  as the other metrics. Captures how far up the list the good passage landed, which matters
  because the model attends unevenly across a long context.
- **nDCG@5** — rank-discounted gain, as a cross-check on MRR.

## Running it

```bash
make eval        # all arms (downloads ~500MB of models on first run)
make eval-fast   # keyword arm only — no model download, runs in seconds
```

The models are an *evaluation* cost, not a production one. `faiss-cpu` and
`sentence-transformers` are in the `dev` dependency group; the served API needs neither,
and the Dockerfile's `uv sync --no-dev` leaves both out of the image. `make eval-fast`
runs the shipped arm alone, which is why it needs no weights.

`--top-k` moves the cutoff, and every metric follows it — `--top-k 10` reports `hit@10`,
`recall@10`, `ndcg@10` and an MRR truncated at 10. The thresholds are calibrated at k=5, so
`--check` only runs at the default cutoff and fails loudly rather than comparing a `hit@10`
against a `hit@5` floor.

Only the shipped arm has a threshold entry. Every other arm is measured and published as
a baseline for comparison, not defended as a quality bar — see [CI gate](#ci-gate).
`--check` names every ungated arm explicitly, and a run in which *nothing* was gated —
`--check --arms dense` — is a failure rather than a pass.

Useful flags:

```bash
uv run python eval/run_eval.py --arms hybrid rerank   # subset
uv run python eval/run_eval.py --split dev            # decide things against this portion
uv run python eval/run_eval.py --split holdout        # what --publish reports
uv run python eval/run_eval.py --failures             # list the questions that missed
uv run python eval/run_eval.py --json results.json    # full per-case output
uv run python eval/run_eval.py --check                # exit 1 below thresholds
uv run python eval/run_eval.py --publish              # refresh the published results
```

`--check` and `--publish` each refuse the other's split. Gating a single split compares a
smaller, noisier sample against floors calibrated on the whole set; publishing `dev` would
put the questions a configuration was chosen on onto the page as evidence about it.

## Results

Everything between the markers below is generated by `--publish` and overwritten on every
run. Do not edit it by hand.

<!-- eval:begin -->
<!-- Generated by eval/publish.py. Do not edit by hand; edits are overwritten. -->

Measured on 73 chunks and the 22 held-out golden questions at `c2d283e`.

| Arm | recall@5 | hit@5 | MRR | ndcg@5 |
|-----|---------:|---------:|---------:|---------:|
| `bm25` _(shipped)_ | **0.775** | **1.000** | **0.901** | **0.801** |
| `dense` | 0.573 | 0.818 | 0.677 | 0.578 |
| `hybrid` | 0.626 | 0.909 | 0.731 | 0.625 |
| `rerank` | 0.622 | 0.864 | 0.784 | 0.650 |
| `bm25+rerank` | 0.697 | 1.000 | 0.845 | 0.713 |

**Production runs Keyword only, which also leads on hit@5 (1.000).**

Best score per column in bold.
<!-- eval:end -->

`--publish` refuses a partial run, a non-default cutoff, or any split but `holdout` —
a published table missing rows is worse than no table at all, and a published number
nothing held back is worse still.

## How the numbers get published

No result is transcribed by hand. See
[ADR-0001](adr/0001-generated-eval-results.md) for the decision and the rejected
alternatives.

```
push to main
   │
   └─ Backend CI · Retrieval eval
        ├─ run_eval.py --check              (all 55 questions — the gate)
        ├─ run_eval.py --split holdout --publish   (the 22 held-out — the report)
        │    ├─ writes frontend/data/evalResults.json
        │    └─ rewrites the marked block above
        └─ commits both back to main
             └─ Vercel redeploys the frontend with the new numbers
```

Two invocations because they measure different samples on purpose: the gate wants the
largest sample it can get, and the report wants the sample nothing was chosen against.

The commit touches only `frontend/data/**` and `docs/evaluation.md`, neither of which
matches this workflow's path filters, so it cannot retrigger the job. Pull-request runs
measure and gate but never publish — branch results would race into the file.

Two consequences worth knowing:

- **No claim about which arm wins is written by hand anywhere.** The project page renders a
  generated verdict line naming the shipped arm and the arm currently leading on the gating
  metric. When the shipped configuration changes, that sentence changes with it.
- **Metrics are not rendered as a time series.** Corpus changes move every metric, so values
  from different corpora are not comparable and a trend line would report corpus growth as
  a quality decline. The findings log carries the history instead, because each entry states
  its own corpus context.

## CI gate

`.github/workflows/backend-ci.yml` runs `scripts/backend-eval.sh` on every backend change.
The job fails if a gated arm falls below the floors in `eval/run_eval.py`, so a change that
degrades retrieval cannot merge silently.

Floors are hit@5 ≥ 0.85 and MRR ≥ 0.75, set below the measured values with headroom for
noise. They are floors, never targets — tuning a parameter until a floor is cleared is
fitting to the golden set.

**Only the shipped arm is gated**, and `THRESHOLDS` looks it up rather than naming it, so
the gate follows production when the shipped arm changes. Two reasons for that line. A
floor exists to stop a change degrading what a visitor is actually served, and nothing is
served by an arm production does not run. And floors are calibrated against a corpus: with
four gated arms, every corpus change means four constants to re-justify, and a constant
nudged to make a build pass is exactly the magic number this harness argues against. The
ungated arms are still measured, still published, and still compared — they are just not
build-breaking.

## What the harness has caught

The first two were in code that looked perfectly reasonable, and neither was visible to any
test. The third was not a bug at all — it was the architecture. They are summarised on the
project page; the full accounts are here.

### The pipeline lost to plain keyword search

The shipped configuration was hybrid retrieval — weighted fusion of semantic and keyword
search — followed by cross-encoder re-ranking. On the corpus as it stands at 73 chunks,
BM25 alone beat it on every metric:

| Arm | recall@5 | hit@5 | MRR | nDCG@5 |
|-----|---------:|------:|----:|-------:|
| `bm25` | **0.690** | **0.982** | 0.885 | **0.740** |
| `dense` | 0.555 | 0.818 | 0.680 | 0.578 |
| `hybrid` | 0.631 | 0.927 | 0.750 | 0.643 |
| `rerank` _(then shipped)_ | 0.611 | 0.909 | 0.859 | 0.682 |
| `bm25+rerank` _(added to answer this)_ | 0.647 | **0.982** | **0.887** | 0.702 |

All 55 questions; best per column in bold. The ordering is the same on each split taken
separately, which is why the conclusion is not an artefact of the questions used to reach
it:

| Arm | hit@5 (dev, 33) | hit@5 (holdout, 22) | MRR (dev) | MRR (holdout) |
|-----|----------------:|--------------------:|----------:|--------------:|
| `bm25` | 0.970 | 1.000 | 0.874 | 0.902 |
| `rerank` | 0.939 | 0.864 | 0.909 | 0.784 |
| `bm25+rerank` | 0.970 | 1.000 | 0.915 | 0.845 |

**Why not retune the weights.** The obvious reaction is to move `DENSE_WEIGHT` /
`SPARSE_WEIGHT`. It is the wrong knob. Under RRF, driving the dense weight toward zero
makes `hybrid` converge on BM25's ordering — and BM25 already led every metric, so
"find the optimal ratio" and "turn dense off" are the same experiment. Retuning is a slower
route to the same answer, and it ends in a magic constant with no principled justification.
The real question was structural: does the dense stage contribute anything here at all?

**The arm that answered it.** `bm25+rerank` feeds BM25 candidates straight to the
cross-encoder, skipping dense entirely. It beat `rerank` on hit@5, recall@5 and nDCG@5 on
every split — 0.982 vs 0.909 overall on the gating metric, and 1.000 vs 0.864 on the
held-out questions. So the dense stage was
contributing nothing the re-ranker could not recover on its own. `hybrid` scoring *below*
`bm25` says more than that: fusion was actively costing recall, displacing good keyword
hits with worse semantic ones.

**Then the same test for the cross-encoder**, judged on hit@5 rather than MRR. hit@5 is the
criterion because the pipeline hands exactly five chunks to the LLM: it decides whether the
model can answer at all, while MRR only describes how far up a chunk that already made the
cut landed. `bm25` and `bm25+rerank` tie on hit@5 on all three samples (0.982 / 0.970 /
1.000), and `bm25` leads on recall@5 and nDCG@5 everywhere. MRR is the one metric where the
re-ranker has a case, and it does not survive the split: ahead on `dev` (0.915 vs 0.874),
behind on `holdout` (0.845 vs 0.902), separated by 0.002 over all 55. That is a wash on
samples this size, and it is a wash on the metric that was never the deciding one. A stage
that cannot move the metric it exists to move does not earn a model load and a forward pass
per query.

This is exactly the comparison the split was introduced for. Judged on `dev` alone the
re-ranker looks like the better MRR choice, and keeping it on that basis would have been
fitting to the questions used to make the decision.

**What changed.** Production retrieval is now `sparse_search` and nothing else. Removing
the dense and re-ranking stages from the serving path took `faiss-cpu` and
`sentence-transformers` out of the production dependency set — 87 locked packages down to
40, and the built image from **17.2GB to 544MB**:

| Image layer | Before | After |
|-------------|-------:|------:|
| `uv sync --no-dev` (dependencies) | 10.5GB | 230MB |
| Baked model weights | 535MB | — |
| `chown` layer (copy-on-write duplicate of the above) | 5.93GB | 130MB |
| **Total** | **17.2GB** | **544MB** |

Most of that was never the models. `sentence-transformers` pulls `torch`, whose default
Linux wheels bring the NVIDIA CUDA runtime with them — several gigabytes of GPU libraries
inside a container that has no GPU — and the `chown -R` layer then duplicated the whole
virtualenv a second time. The measured decision to drop the dense stage is what made that
visible; nobody was going to notice it from reading the Dockerfile.

`RAGPipeline` still implements every stage, because the harness measures them, but imports
both libraries lazily inside the loaders rather than at module scope. That is what lets one
module serve a container where neither library is installed and still implement the arms
that need them; `test_the_pipeline_module_imports_without_the_eval_only_libraries` runs the
import in a subprocess with both blocked, because a module-level import would pass every
other test here and crash only on deploy.

Cheaper *and* better is a stronger outcome than a retuned constant, and it is not the
outcome the architecture was built expecting.

The decision, its rejected alternatives, and the two structural changes that came with it
— gating only the shipped arm, and splitting the golden set — are recorded in
[ADR-0004](adr/0004-retrieval-shipped-arm-chosen-by-measurement.md).

**What was deliberately not concluded.** That hybrid retrieval and re-ranking are not worth
running. This corpus embeds its own expected questions: `docs/chatbot-questions.md` is
written as recruiter Q&A, and the golden set asks paraphrases of it. That is precisely the
condition that flatters lexical matching, and relevance is labelled by phrase presence,
which is close to what BM25 ranks by. The result is about *this* corpus. Every retired arm
stays in the harness so that the day this stops being true, a measurement says so rather
than a rebuild from scratch.

**Consequence worth knowing.** BM25-only retrieval returns nothing when a query shares no
term with any chunk, where hybrid always returned its top five. That is the preferable
failure here: an empty context leaves the system prompt's "say so honestly" instruction
unopposed, rather than handing the model five irrelevant chunks to sound confident from.

### The tokenizer was silently destroying keyword recall

The index builder and the query path both tokenized with `text.lower().split()`. That never
matches "engineering" against "engineer", never matches "David's" against "David", leaves
punctuation welded to terms, and scores stopwords as if they carried meaning.

Replacing it with a stopword-filtered, Snowball-stemmed tokenizer moved the keyword arm's
MRR from 0.745 to 0.892 — roughly 20% relative — at no query-time cost. Measured against
the same corpus:

| Tokenizer | recall@5 | hit@5 | MRR | nDCG@5 |
|-----------|---------:|------:|----:|-------:|
| `.lower().split()` | 0.633 | 0.945 | 0.745 | 0.618 |
| stopwords + Snowball stemming | 0.730 | 1.000 | 0.892 | 0.758 |
| change | +0.097 | +0.055 | +0.147 | +0.140 |

The operative word is *shared*. Index-time and query-time tokenization must match exactly —
a mismatch is unfixable at query time, because the terms the query is looking for were never
written into the index. Both sides import the single implementation in
`app/rag/tokenize.py`.

### A textbook constant, used at the wrong scale, disabled half the system

Reciprocal-rank fusion combines ranked lists as `weight / (k + rank)`, and the textbook
value for `k` is 60. That default assumes lists thousands of documents long.

Over the ten-item lists here, `k=60` varies the rank term by only 1.15× across the entire
list, while the 0.7/0.3 arm weights vary by 2.33×. The weights dominated outright: every
dense hit outscored every sparse hit, so the keyword retriever could never introduce a
candidate the dense arm had missed — which is the only reason to run a second retriever at
all. Fusion was running, passing its tests, and contributing nothing. Dropping `k` to 1
restored it.

Nothing about the code looked wrong, and no unit test could have caught it: every component
behaved exactly as specified. Only a metric moved.

## Scope, and honesty about it

The corpus is small enough that retrieving ten candidates touches a meaningful fraction of
it, so this is not a hard retrieval problem and the absolute numbers should be read with
that in mind. The pipeline is built at production complexity — hybrid retrieval,
cross-encoder re-ranking, a measured regression gate — deliberately, to demonstrate the
pattern on a corpus small enough to label exhaustively by hand.

Two structural biases narrow what the comparison can claim:

1. **The corpus contains the questions.** `docs/chatbot-questions.md` is written as
   recruiter questions with answers, and the golden set asks paraphrases of those same
   questions. Lexical overlap between query and document is therefore unusually high. Dense
   retrieval earns its keep when the user's phrasing shares no vocabulary with the source —
   a case a Q&A corpus under-represents by construction.
2. **The labels correlate with one of the arms.** Relevance is defined by exact phrase
   presence, and BM25 ranks by exact term overlap, so the labelling scheme and the keyword
   arm measure something close to the same thing. Every arm is scored against identical
   labels, so the comparison is internally fair — but any conclusion drawn from it is about
   *this* corpus, not about retrieval in general.

The golden set no longer serves as both development signal and published result. It is
split into `dev` and `holdout`, decisions are made against `dev`, and `--publish` reports
`holdout` only — see [Splits](#method). The published sample is 22 questions, which is
small; the numbers should be read with that in mind.

## Not yet measured

Retrieval quality is only half of a RAG system's behaviour. Still open: generation
faithfulness (does the answer stay inside the retrieved context?), refusal behaviour on
out-of-scope questions, and adversarial/prompt-injection robustness.
