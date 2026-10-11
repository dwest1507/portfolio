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
relevant if any of them appears in its text beginning at the start of a word (case- and
whitespace-insensitive). A phrase may end mid-word, so `mentor` matches "mentoring" and
`rate limit` matches "rate limiting", but `no` does not match "know" and `R:` does not
match "ER:". Labelling by phrase rather than by chunk ID means the golden set stays valid
when the corpus is re-chunked or re-indexed, which chunk IDs would not survive.

**Breadth lint** — a phrase that marks a large share of the corpus relevant hands every arm
a hit whatever it retrieved, so it is a labelling defect rather than a label.
`test_the_committed_golden_set_has_no_overbroad_phrase` fails when any phrase matches more
than 15% of corpus chunks (`MAX_PHRASE_SHARE` in `run_eval.py`). The fix is to narrow the
phrase to what the question and corpus text justify. A phrase that is broad but correct,
such as the current employer's name, goes on `breadthAllowList` in `golden_set.json` with
its reason instead. A held-out case's phrases may be repaired only for reasons independent
of any arm's results, such as this lint, and never with those results in view.

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

**Splits** — the golden set is partitioned into a `dev` portion (54 questions) and a
`holdout` portion (33). Parameters, weights and stage choices are decided against `dev`.
`holdout` is what `--publish` reports, so no number on the public page is the score of a
configuration that was chosen using those same questions. `--split` selects the portion.

Assignment is deterministic rather than hand-picked: a case is held out when
`sha256(salt + ":" + id)` sorts below the `holdoutBelow` boundary recorded in
`golden_set.json`. The labels are *recorded* in the file rather than recomputed at run
time, because a frozen split is the entire point — and the rule is written so the two can
never disagree. It reads one id at a time, so a case's portion depends on its own id and
nothing else; adding, removing or renaming other questions cannot move it.

That is why the boundary is a hash threshold and not "the first 40% by rank". A rank-based
cutoff moves with the size of the set, so every question added would push some case across
the line — and `test_the_recorded_split_matches_the_documented_rule`, which recomputes the
rule to catch a question quietly hand-edited across it, would then be the thing demanding
that the frozen labels be rewritten, leaking held-out questions into `dev` through the
check meant to prevent exactly that. The boundary in the file (`0x5…`, 5/16 of the hash
space) is the round value that reproduces the original 33/22 draw exactly, so recording it
moved no question.

The trade is sample size. 33 questions move hit@5 in steps of about 0.030, so the
published numbers are coarser than a run over all 87 would be. That is the price of them
measuring something rather than scoring the winner of their own selection.

**Query categories** — cases are classified by their lexical and conceptual relationship to
the corpus into `direct` (in-vocabulary questions matching corpus wording), `paraphrase`
(out-of-vocabulary factual questions deliberately avoiding corpus keywords), and `conceptual`
(thematic or cross-project synthesis queries). The 55 founding cases are all `direct`,
complemented by 16 `paraphrase` and 16 `conceptual` questions.
Schema Version 3 documents publish per-category metric breakdowns (`byCategory`) alongside
aggregate numbers to diagnose lexical versus semantic retrieval performance. See
[ADR-0005](adr/0005-query-categories-for-rag-evaluation.md).

**Noise-aware verdict** — a gap of one or two questions out of 33 is sampling noise, so the
Verdict Line no longer names whichever arm scores highest. Each arm is compared with the
shipped arm on the gating metric, question by question: `won` counts the questions only
that arm hit, `lost` the questions only the shipped arm hit, and questions both hit or both
missed carry no information about which is better. An exact two-sided sign test (McNemar's
exact test) on that split calls the arm `ahead` or `behind` only at p < 0.05; otherwise it
is `indistinguishable`, and the Verdict Line says no arm is distinguishable and names the
sample size. At least six discordant questions are needed before anything can be called
(5–0 gives p = 0.0625), so on the held-out sample "indistinguishable" is the usual, honest
answer. Schema Version 4 documents carry the comparison per arm (`vsShipped`) and per Query
Category (`vsShippedByCategory`), plus a seeded 95% bootstrap interval for MRR
(`mrrInterval`). The Scoreboard and the table below render the won/lost counts; the MRR
interval is rendered here only, not on the project page. See
[ADR-0006](adr/0006-noise-aware-verdict-line.md).

**Out-of-Scope Cases** — 20 cases (`answerable: false`) ask what a visitor might reasonably
ask but the corpus cannot answer: salary expectations, languages and tools David has not
used, hobbies. They exist for the generation eval, where the right answer is a Decline.
They carry no `relevant_phrases`, `required_facts` or category, and share the same hash
split rule (14 dev / 6 held-out). The retrieval harness excludes them by that label before
scoring, so there is nothing to retrieve for them, and reports them in its summary line
(`Golden set: 87 answerable + 20 out-of-scope questions (all)`). They are not caught by
the "matches no chunk" error, which stays loud for a broken label on an answerable case.
`select_cases` rejects an answerable case with no phrases and an Out-of-Scope Case that
carries labels. Every split count, metric and published `goldenQuestions` in this document
counts answerable cases only.

**Generation fields** — each case may also carry `answerable` (default `true`),
`required_facts`, and `origin` (`authored` or `visitor`, default `authored`) so results on
real visitor questions can be reported separately. `required_facts` are the statements a
correct answer conveys, read by the generation harness for Fact Recall and judged on
meaning rather than wording. Every answerable case carries at least one (`select_cases`
rejects one with none), each a self-contained sentence that names its subject ("David holds
the CompTIA Security+ certification.", not "He holds Security+."), because the Judge reads
it beside an answer with no question in view. They are written from the question and the
corpus only, never with any arm's answers in view, and David reviews every one: they are
facts about him. See [ADR-0007](adr/0007-generation-evaluation-harness.md).

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

Measured on 120 chunks and the 33 held-out golden questions at `589d3c2`.

| Arm | recall@5 | hit@5 | MRR | ndcg@5 | MRR 95% CI | vs shipped (won / lost) |
|-----|---------:|---------:|---------:|---------:|---------:|---------:|
| `bm25` _(shipped)_ | **0.552** | 0.879 | **0.841** | **0.689** | 0.712–0.947 | — |
| `dense` | 0.439 | 0.818 | 0.648 | 0.503 | 0.500–0.784 | 2 / 4 |
| `hybrid` | 0.493 | **0.909** | 0.705 | 0.565 | 0.573–0.823 | 2 / 1 |
| `rerank` | 0.522 | **0.909** | 0.809 | 0.639 | 0.688–0.915 | 2 / 1 |
| `bm25+rerank` | 0.548 | **0.909** | 0.795 | 0.662 | 0.674–0.894 | 1 / 0 |

**Production runs Keyword only. Across the 33 held-out questions, no other arm is distinguishable from it on hit@5.**

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
        ├─ run_eval.py --check              (all 87 questions — the gate)
        ├─ run_eval.py --split holdout --publish   (the 33 held-out — the report)
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
  generated verdict line naming the shipped arm and any arm distinguishably ahead of or
  behind it on the gating metric — and, when none is, saying so along with the sample size.
  When the shipped configuration or the numbers change, that sentence changes with it.
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
test. The third was not a bug at all — it was the architecture. The fourth was empirical bias
in the evaluation set itself. They are summarised on the project page; the full accounts are here.

### Query categories expose where semantic retrieval excels

When evaluated on the founding 55 direct questions, keyword search beat the hybrid and dense
pipelines across every metric because those questions shared vocabulary with the recruiter Q&A
in the Corpus. Partitioning the Golden Set into `direct`, `paraphrase`, and `conceptual` categories
(87 questions total) revealed the exact boundary where lexical search fails and semantic search
is required:

| Category | Questions | BM25 hit@5 | Hybrid hit@5 | Re-rank hit@5 | Re-rank MRR vs BM25 MRR |
|----------|----------:|-----------:|-------------:|--------------:|------------------------:|
| `direct` | 55 | **0.964** | **0.964** | 0.945 | 0.888 vs 0.878 |
| `paraphrase` | 16 | 0.875 | **0.938** | **0.938** | **0.828** vs 0.617 (+0.211) |
| `conceptual` | 16 | **0.750** | 0.688 | 0.688 | 0.523 vs 0.526 |
| **All** | **87** | **0.908** | **0.908** | 0.897 | 0.810 vs 0.765 |

On out-of-vocabulary paraphrases, keyword search dropped from 0.964 to 0.875 hit@5, while hybrid
and cross-encoder re-ranking achieved 0.938 hit@5 and lifted MRR from 0.617 to 0.828. Conceptual
synthesis queries proved challenging across all models (hit@5 0.625–0.750), with `bm25+rerank`
leading on MRR (0.575).

Production remains on BM25 for its sub-second execution, tiny footprint, and 0.908 aggregate hit rate
(clearing the 0.85 floor), but the categorized benchmark proves that dense and re-ranking stages
provide demonstrable recovery on queries phrased without Corpus keywords.

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
`holdout` only — see [Splits](#method). The published sample is 33 questions, which is
small; the numbers should be read with that in mind.

## Generation baseline

Before generation moves from Groq to OpenAI
([ADR-0008](adr/0008-generation-moves-to-openai.md)), the current model's answers are
captured while Groq's free tier still serves it. `eval/run_generation.py` runs every
Golden Set case (both Splits, answerable and Out-of-Scope) through production retrieval
(the Shipped Arm) and `GROQ_MODEL`, and commits `backend/eval/baselines/groq.json`:

- per case, the answer, the exact retrieved chunk texts, billed usage, and the model ID
  Groq reports answering with;
- the requested model, Arm, temperature, `max_tokens`, Corpus size and commit it was
  measured at.

Nothing in it is judged yet. Keeping the contexts is the point: a Judge can score the
record later, and OpenAI candidates can replay identical contexts, so the model is the
only variable.

The generator has no prompt of its own. It builds messages with the production
`build_messages` and samples with production's `TEMPERATURE` (0) and `MAX_TOKENS`, and a
test asserts it sends exactly what `/api/chat` sends for the same question and chunks.
Production generates at temperature 0 for the same reason
([ADR-0007](adr/0007-generation-evaluation-harness.md)): the eval should measure what
visitors are served.

Groq's free tier (8k tokens/min, 200k tokens/day) is shared with visitors, so calls are
paced to 7k billed tokens a minute and the run stops before passing a 180k-token budget.
Each answer is written as it arrives, so a run stopped by the budget resumes where it left
off the next day. The committed baseline (107 cases, `openai/gpt-oss-120b`) billed 132,249
tokens in one run. The record refuses to resume across a changed model, Arm, sampling
settings or Corpus size.

```bash
cd backend
uv run --frozen python eval/run_generation.py   # capture, or resume a partial record
```

The harness entry point, `run_generation` in `eval/generation.py`, takes the cases, a
retriever, a generator and optionally a Judge, all injected, and is tested with fakes.

## Judging answers

The Judge is TypeSafe's Jev, pinned to `jev-1.13.0`, never `jev-latest`
([ADR-0007](adr/0007-generation-evaluation-harness.md)). `eval/judge.py` sends every
request with the pinned version and refuses an answer from any other version, so a
judged run records the version that actually judged it. The Judge interface has one
method per judgment, each asked about the smallest input that answers it:

| Judgment | Asked about | Answer |
|---|---|---|
| Declines | the question and the whole answer | yes / no |
| Is factual | one sentence | yes / no (no = filler) |
| Relation | one sentence and one retrieved chunk | supports / contradicts / says nothing |
| Conveys | the whole answer and one Required Fact | yes / no |

Per case, the answer is first asked whether it Declines. A Decline, and any answer to
an Out-of-Scope Case, is judged no further: the Judge is weak on negation, so "the
information doesn't include that" would otherwise count as an unsupported claim. Every other answer is split into sentences in code,
filler is dropped, and each factual sentence is judged against each retrieved chunk
separately. One supporting chunk is enough.

Sentences are split so that each states its claim on its own. A list item ("SQLite")
is judged together with the line introducing its list ("David has worked with the
following databases: SQLite"), and a table row is judged as one claim with each cell
labelled by its column heading. Markdown emphasis is removed, and "e.g." ends no
sentence.

| Metric | Definition |
|---|---|
| Fact Recall | Required Facts conveyed / Required Facts, over every answerable case |
| Faithfulness | supported factual sentences / factual sentences, over answerable cases that did not Decline |
| Contradictions | every (sentence, chunk) pair judged `contradicts`, listed individually |
| Decline accuracy | correct / all cases, where declining an Out-of-Scope Case and answering an answerable one are both correct; also reported in each direction |

A declined answerable case conveys none of its Required Facts, so it counts against both
Fact Recall and Decline accuracy. Declining a fair question can't make Fact Recall look
better. A Decline states nothing, so it leaves Faithfulness untouched.

A stored record, such as the Groq baseline, is judged without regenerating it: each
case is replayed from the record, so the Judge sees the answer the model gave and the
exact chunks it was given.

```bash
cd backend
uv run --frozen python eval/judge_generation.py                                  # all cases
uv run --frozen python eval/judge_generation.py --split dev --output judged.json
```

This needs `JEV_API_KEY`. The CLI prints the metrics and then each Contradiction with
its case, sentence and chunk. `--output` writes the same, plus per-case judgments, the
Judge version, Jev's billed usage and the judged record's provenance, as JSON. Judged
runs are not committed or published yet, and nothing is gated.

## Validating the Judge

Before a Judge result gates anything, its verdicts are compared with hand labels
([ADR-0007](adr/0007-generation-evaluation-harness.md)). `backend/eval/judge_validation.json`
holds 32 sentences from the Groq baseline's answers, each labelled against the chunks its
answer was written from:

| Label | Meaning |
|---|---|
| filler | states nothing about David: a pleasantry, heading, transition, or a remark about the context |
| supported | every claim in it is stated or clearly implied by the chunks, together if not by one |
| contradicted | a chunk states the opposite of a claim in it |
| says nothing | neither: at least one claim has no basis in the chunks, and none is contradicted |

Each sentence is also marked compound (several claims) or single. 23 of the 32 are
compound on purpose: if Jev's disagreements cluster there, that is the case for an LLM
step that splits answers into atomic claims, rejected for now in ADR-0007. A test fails if
a labelled sentence is no longer one the harness's splitter produces from its stored
answer, so the labels cannot quietly drift away from what is judged.

`eval/validate_judge.py` runs every labelled sentence through the harness's own sentence
judgment and reports two agreements, one per thing a judged run outputs:

- **Faithfulness agreement**: filler, supported or unsupported, where contradicted and
  says-nothing both count as unsupported;
- **Contradiction agreement**: whether a Contradiction is listed for the sentence.

It then lists every disagreement with Jev's per-chunk relations, and counts disagreements
separately for compound and single sentences.

```bash
cd backend
uv run --frozen python eval/validate_judge.py --output validation-run.json
```

The labels were drafted before any of Jev's judgments of these sentences were looked at,
then reviewed by David. The CLI refuses to measure against labels whose `status` is not
`reviewed` (`--draft` overrides).

### Result: Jev is not yet fit to gate Faithfulness

Measured 2026-10-10 with `jev-1.13.0` at `14ba262`:

| | Agreement |
|---|---|
| Faithfulness | **0.750** (24 of 32) |
| Contradictions | 0.906 (29 of 32) |

The headline rate hides where the errors fall. Jev's Faithfulness verdict against the
hand labels:

| Hand label | Jev: filler | Jev: supported | Jev: unsupported |
|---|---|---|---|
| filler (3) | 3 | 0 | 0 |
| supported (22) | 1 | 21 | 0 |
| unsupported (7: 6 says nothing, 1 contradicted) | 3 | **4** | **0** |

Jev agrees on nearly every supported and filler sentence, and calls **none** of the seven
unsupported sentences unsupported. Each error makes Faithfulness look better than it is,
so a Faithfulness gate built on it would not fire when answers start inventing things.
(If Jev caught half of unsupported sentences, seeing 0 of 7 would happen less than 1% of
the time, so 32 sentences are enough to show this.) The 8 Faithfulness disagreements
have two causes:

1. **Factual sentences dropped as filler (4).** "It uses RAG over the complete corpus of
   Nietzsche's 18 works…", "Each deployment includes an automated evaluation pipeline…",
   "The system enforces several safeguards: … a hard 5-second timeout…", "These intervals
   are incorporated into the deployment gate…". Each states a fact about a project or
   system without naming David, and the filler question asks about "a fact about
   David". A dropped sentence is never checked against a chunk. This hid the set's one
   real contradiction (18 works, where the chunk says 19). This is a wording problem in
   `FACTUAL_QUESTION`, not a compound-sentence problem.
2. **Partly supported sentences judged supported (4).** "SQS, SNS, EventBridge", "Modal,
   Groq, or GPU containers on Railway", the separate "inference" image, and "CloudWatch
   alerts track compliance-related events". In each, a chunk supports part of the
   sentence, and Jev calls the whole sentence supported. All four are compound.

**Do disagreements cluster on compound sentences?** All 8 Faithfulness disagreements are
on compound sentences (8 of 23, against 0 of 9 single). The comparison is confounded,
though: every unsupported sentence in the set is compound, and the four filler errors
have nothing to do with how many claims a sentence makes. The four partly supported
sentences are the real compound-sentence failure. They count as a reason to revisit LLM
claim splitting (ADR-0007), for this reason. Asking "supports" strictly (every part)
would fix them, but it would also fail the sentences whose claims are each supported by
a different chunk. Jev now judges all five of those correctly as supported, so the current
leniency may be what gets them right. Only splitting a sentence into claims, each checked
against every chunk, handles both.

**Contradictions.** Jev listed two that aren't there, the same two seen when the Groq
baseline was first judged. A chunk naming a *different* item of the same kind is taken
to contradict: a Security+-only list "contradicts" the DataCamp certificate, and the
chatbot's "hosted on Groq" "contradicts" David having used Claude. It missed the one real
contradiction because it dropped that sentence as filler. Contradictions are not gated.

**What follows.** Faithfulness should not gate (#71) until Jev's questions are fixed
and revalidated against these labels: the filler question widened to facts about
David's projects and systems; `contradicts` limited to incompatible statements about the
same thing; and the partly supported failure fixed by a stricter `supports` criterion or
by claim splitting. Changing a Judge question is a new measurement, so the run-to-run
spread below is rerun after any of these. Decline accuracy uses a separate judgment that
this set does not test.

## Run-to-run spread

The same commit does not give the same numbers twice: Jev is not fully deterministic, and
OpenAI's reasoning models generate only at the default temperature. The spread of three
runs sets two things ([ADR-0007](adr/0007-generation-evaluation-harness.md)):

- the **rounding step** for published generation metrics, from the held-out spread
  (held-out is what is published): the smallest of 0.005 / 0.01 / 0.02 / 0.05 / 0.1 no
  smaller than any published metric's range;
- the **Floors** for Faithfulness and Decline accuracy, from the spread over every case
  (the gate runs on the full Golden Set): the lowest run minus twice the range (three runs
  understate the noise), and at least one step, rounded down to the step.

Measured on 2026-10-10 at commit `060c340`: `gpt-6-luna` with reasoning effort `low`, the
`bm25` Arm, 123 Corpus Chunks, all 107 cases, judged by `jev-1.13.0`.

**Judge only.** One Luna record, judged three times:

| Metric | Held-out | Range | All cases | Range |
|---|---|---|---|---|
| Fact Recall | 0.736, 0.736, 0.747 | 0.011 | 0.741, 0.737, 0.741 | 0.005 |
| Faithfulness | 0.981, 0.981, 0.981 | 0 | 0.992, 0.992, 0.984 | 0.008 |
| Decline accuracy | 1.000, 1.000, 1.000 | 0 | 0.953, 0.953, 0.953 | 0 |

**End to end.** Three Luna generations of the same commit, each judged once:

| Metric | Held-out | Range | All cases | Range |
|---|---|---|---|---|
| Fact Recall | 0.736, 0.736, 0.747 | 0.011 | 0.741, 0.741, 0.727 | 0.015 |
| Faithfulness | 0.981, 1.000, 1.000 | 0.019 | 0.992, 0.992, 0.992 | 0.000 |
| Decline accuracy | 1.000, 1.000, 1.000 | 0 | 0.953, 0.953, 0.944 | 0.009 |

Only 7 of the 107 answers were word-for-word the same in all three generations. The
metrics hardly move all the same, because a reworded answer mostly makes the same claims.
The largest held-out range is Faithfulness at 0.019, one of ~52 factual sentences
changing verdict. Derived from the end-to-end runs, which include the Judge's noise:

| | Value | Derivation |
|---|---|---|
| Rounding step | **0.02** | smallest step ≥ 0.019 |
| Faithfulness Floor | **0.96** | 0.992 − max(2 × 0.000, 0.02) = 0.972, rounded down to 0.96 |
| Decline accuracy Floor | **0.92** | 0.944 − max(2 × 0.009, 0.02) = 0.924, rounded down to 0.92 |

The Judge-only runs give the same three numbers. These Floors were measured with Judge
questions that [validation](#result-jev-is-not-yet-fit-to-gate-faithfulness) found blind
to unsupported sentences. They stand only until those questions change, at which point
the study is rerun. On full-set ranges this small, the
one-step minimum headroom sets both Floors. A change to the Judge's questions, the
generation model or its reasoning effort is a new measurement, and the study is rerun:

```bash
cd backend
uv run --frozen python eval/run_generation.py --provider openai --record runs/luna-1.json
uv run --frozen python eval/judge_generation.py --record runs/luna-1.json --output runs/judged-1.json
# ... three of each, then:
uv run --frozen python eval/variance.py runs/judged-1.json runs/judged-2.json runs/judged-3.json
```

`--provider openai` sends no temperature (the candidates reject any but the default) and
pins `--reasoning-effort` (default `low`). It needs `OPENAI_CI_API_KEY` and a `--record`
path, so it cannot overwrite the Groq baseline. A Luna run of all 107 cases billed ~108k
tokens; judging one costs Jev ~590k input tokens.

## Not yet measured

Retrieval quality is only half of a RAG system's behaviour. Generation can now be
judged, but nothing published or gated relies on it yet. Still open: fixing the Judge's
questions that validation found blind to unsupported sentences, then the generation gate
and published results, and adversarial/prompt-injection robustness.
