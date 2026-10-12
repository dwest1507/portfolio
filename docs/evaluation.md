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

**Candidate and Reference Arms** — every arm carries an `eligibility` in `ARM_SPECS`,
published with the Scoreboard. A *Candidate Arm* could become the shipped arm without
bringing a GPU-oriented ML runtime back into the production image; a *Reference Arm* is a
baseline kept for comparison that cannot ship as built. Only Candidate Arms are eligible
when the shipped arm is chosen ([ADR-0009](adr/0009-shipped-arm-selection-rule.md)).
`test_a_candidate_arm_loads_no_torch_model` holds the line: nothing a Candidate Arm loads
may need torch.

| Arm | Eligibility | What it runs |
|-----|-------------|--------------|
| `bm25` | Candidate | BM25 alone, no model. The shipped arm. |
| `dense`, `hybrid`, `rerank`, `bm25+rerank` | Reference | The torch models through sentence-transformers. Definitions unchanged. |
| `onnx-dense` | Candidate | `dense` with the same all-mpnet-base-v2 model on ONNX Runtime. |
| `onnx-hybrid` | Candidate | `hybrid` with `onnx-dense` as its dense stage: same weights, same `RRF_K`. |
| `bm25+onnx-rerank-20` | Candidate | 20 BM25 candidates, narrowed to k by ms-marco-MiniLM-L-6-v2 on ONNX Runtime. |

The ONNX arms run the publishers' own ONNX exports of the two models
(`backend/app/rag/onnx_models.py`), pinned to exact Hub revisions so an upstream re-export
cannot silently change a Measured Run. `scripts/build_index.py` embeds the Corpus with the
ONNX embedder into `indexes/onnx_embeddings.npy`, so an arm's load band counts loading the
model, not embedding the Corpus. `onnx-dense` searches that matrix with one exact inner
product rather than FAISS: numpy is already on the serving path. The re-ranking pool of
`bm25+onnx-rerank-20` is fixed at 20 (`RERANK_POOL` in `run_eval.py`), not a multiple of k.
The 2×k pool of the older re-ranking arms can only recover chunks BM25 already ranked in its
top 10, and widening it makes a new arm rather than an edit to theirs, so their past
measurements keep their meaning. onnxruntime, tokenizers and huggingface-hub stay in the
`dev` dependency group until an arm built on them is chosen to ship.

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

The trade is sample size. 43 questions move hit@5 in steps of about 0.023, so the
published numbers are coarser than a run over all 111 would be. That is the price of them
measuring something rather than scoring the winner of their own selection.

**Query categories** — cases are classified by their lexical and conceptual relationship to
the corpus into `direct` (in-vocabulary questions matching corpus wording), `paraphrase`
(factual questions asked in words other than the corpus's own), and `conceptual`
(thematic or cross-project synthesis queries). The 55 founding cases are all `direct`,
complemented by 30 `paraphrase` and 26 `conceptual` questions. Only questions Arms disagree
on can tell them apart, and those are almost all paraphrase and conceptual, so these two
categories grow toward ~50 each in reviewed batches while `direct` grows only to cover new
corpus content. Since the 2026-10-09 amendment to ADR-0005, new cases are phrased as a
recruiter or engineer would actually ask rather than by avoiding corpus keywords, are
written without any Arm's results in view, and each targets a different part of the corpus:
a test fails if two paraphrase or conceptual cases mark exactly the same chunks relevant,
since every Arm would hit or miss them together.
Schema Version 3 documents publish per-category metric breakdowns (`byCategory`) alongside
aggregate numbers to diagnose lexical versus semantic retrieval performance. See
[ADR-0005](adr/0005-query-categories-for-rag-evaluation.md).

**Noise-aware verdict** — a gap of one or two questions out of 43 is sampling noise, so the
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

**Latency Bands** — each arm is timed two ways. *Warm*: every answerable question is
timed once, after one untimed warm-up query, because the models load lazily and an arm's
first query is a model load. *Load*: on a fresh pipeline, the time to read the indexes and
load the models the arm needs before its first answer, measured after every arm has run so
a first-ever run times loading, not downloading. Raw timings move between runs and
runners, so what is published is each timing's Latency Band: its nearest power of ten
(`~1ms`, `~10ms`, `~100ms`, `~1s`, `~10s`), cut at the geometric midpoints (3.16ms,
31.6ms, 316ms, 3.16s). Anything under a millisecond is `~1ms`. `~10s` sits above the four
bands the spec named because loading both the embedding model and the cross-encoder takes
~4s, and `~1s` would understate it. The warm band is taken from the p95. Each arm's
`latencyBand` (`warm`, `load`) is part of the measured keys, so only a change of band
rewrites the published results. The raw p50/p95 and load time appear in the CLI's latency
table and in `--json` output only. An arm near a cut can flip bands between runs:
`bm25+rerank`'s warm p95 has measured both 29.6ms and 38ms, either side of 31.6ms.

**Out-of-Scope Cases** — 20 cases (`answerable: false`) ask what a visitor might reasonably
ask but the corpus cannot answer: salary expectations, languages and tools David has not
used, hobbies. They exist for the generation eval, where the right answer is a Decline.
They carry no `relevant_phrases`, `required_facts` or category, and share the same hash
split rule (14 dev / 6 held-out). The retrieval harness excludes them by that label before
scoring, so there is nothing to retrieve for them, and reports them in its summary line
(`Golden set: 111 answerable + 20 out-of-scope questions (all)`). They are not caught by
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
facts about him. See [ADR-0007](adr/0007-generation-evaluation-harness.md). A `visitor`
case starts as a question from production's visitor query log and is promoted only by hand,
after it is read, scrubbed and labelled
([chatbot-rag.md](chatbot-rag.md#promoting-a-logged-question-into-the-golden-set),
[ADR-0010](adr/0010-visitor-queries-logged-with-notice.md)).

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
make eval        # all arms (downloads ~1GB of models on first run: torch and ONNX)
make eval-fast   # keyword arm only — no model download, runs in seconds
```

The models are an *evaluation* cost, not a production one. `faiss-cpu`,
`sentence-transformers`, `onnxruntime`, `tokenizers` and `huggingface-hub` are in the `dev`
dependency group; the served API needs none of them, and the Dockerfile's
`uv sync --no-dev` leaves them out of the image. `make eval-fast`
runs the shipped arm alone, which is why it needs no weights.

`--top-k` moves the cutoff, and every metric follows it — `--top-k 10` reports `hit@10`,
`recall@10`, `ndcg@10` and an MRR truncated at 10. The Floors are derived at k=5, so
`--check` only runs at the default cutoff and fails loudly rather than comparing a `hit@10`
against a `hit@5` Floor.

Only the shipped arm has Floors. Every other arm is measured and published as
a baseline for comparison, not defended as a quality bar — see [CI gate](#ci-gate).
`--check` names every ungated arm explicitly, and a run in which *nothing* was gated —
`--check --arms dense` — is a failure rather than a pass.

Useful flags:

```bash
uv run python eval/run_eval.py --arms hybrid rerank   # subset
uv run python eval/run_eval.py --split dev            # decide things against this portion
uv run python eval/run_eval.py --split holdout        # what --publish reports
uv run python eval/run_eval.py --failures             # list the questions that missed
uv run python eval/run_eval.py --json results.json    # full per-case output and raw timings
uv run python eval/run_eval.py --check                # exit 1 if stale or below a Floor
uv run python eval/run_eval.py --publish              # refresh the published results
```

`--check` and `--publish` each refuse the other's split. Gating a single split compares a
smaller, noisier sample against Floors derived on the whole set; publishing `dev` would
put the questions a configuration was chosen on onto the page as evidence about it.

## Results

Everything between the markers below is generated by `--publish` and overwritten on every
run. Do not edit it by hand.

<!-- eval:begin -->
<!-- Generated by eval/publish.py. Do not edit by hand; edits are overwritten. -->

Measured on 158 chunks and the 43 held-out golden questions at `15db05d` — [CI run](https://github.com/dwest1507/portfolio/actions/runs/38286766752).

| Arm | Eligibility | recall@5 | hit@5 | MRR | ndcg@5 | MRR 95% CI | vs shipped (won / lost) | Latency Band (warm p95) | Load band |
|-----|-------------|---------:|---------:|---------:|---------:|---------:|---------:|---------:|---------:|
| `bm25` _(shipped)_ | Candidate | 0.572 | 0.814 | 0.707 | 0.628 | 0.581–0.828 | — | ~1ms | ~1ms |
| `dense` | Reference | 0.496 | 0.744 | 0.606 | 0.514 | 0.472–0.731 | 4 / 7 | ~100ms | ~1s |
| `hybrid` | Reference | 0.554 | **0.884** | 0.638 | 0.547 | 0.519–0.752 | 4 / 1 | ~100ms | ~1s |
| `rerank` | Reference | 0.588 | 0.861 | **0.764** | 0.647 | 0.639–0.868 | 3 / 1 | ~1s | ~1s |
| `bm25+rerank` | Reference | **0.590** | 0.837 | 0.757 | **0.651** | 0.628–0.868 | 2 / 1 | ~1s | ~1s |
| `onnx-dense` | Candidate | 0.496 | 0.744 | 0.606 | 0.514 | 0.472–0.731 | 4 / 7 | ~10ms | ~100ms |
| `onnx-hybrid` | Candidate | 0.554 | **0.884** | 0.638 | 0.547 | 0.519–0.752 | 4 / 1 | ~10ms | ~100ms |
| `bm25+onnx-rerank-20` | Candidate | 0.584 | 0.861 | 0.762 | 0.644 | 0.639–0.872 | 3 / 1 | ~1s | ~100ms |

**Production runs Keyword only. Across the 43 held-out questions, no other arm is distinguishable from it on hit@5.**

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
        ├─ run_eval.py --check              (all 111 questions — the gate)
        ├─ run_eval.py --split holdout --publish   (the 43 held-out — the report)
        │    ├─ writes frontend/data/evalResults.json
        │    └─ rewrites the marked block above
        └─ commits both back to main
             └─ Vercel redeploys the frontend with the new numbers
```

Two invocations because they measure different samples on purpose: the gate wants the
largest sample it can get, and the report wants the sample nothing was chosen against.

The commit is pushed by the eval-publisher GitHub App, the one actor allowed past `main`'s
pull-request rule (ADR-0001). It touches only `frontend/data/**` and `docs/evaluation.md`,
neither of which matches this workflow's path filters, so it cannot retrigger the job. Pull-request runs
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
The job fails if the shipped arm falls below a Floor, so a change that degrades retrieval
cannot merge silently. The Floors live in one committed record,
`backend/eval/floors/retrieval.json`, and nowhere in code. They are Floors, never
targets — tuning a parameter until a Floor is cleared is fitting to the golden set.

### How the Floors are derived

A Floor is derived by a fixed rule, never chosen
([ADR-0012](adr/0012-recalibration.md)):

> Floor = measured − 2/n, rounded down to 0.005, where n is the answerable cases on the
> full Golden Set, measured on the shipped arm only.

Two cases' worth states the tolerated regression in questions. Retrieval is
deterministic, so the margin is a tolerance for a small real loss, not headroom for noise.
On today's set, BM25 over 111 answerable cases (158 chunks, measured at `324af00`):

| Metric | Measured | − 2/111 | Floor |
|--------|---------:|--------:|------:|
| hit@5 | 0.864865 (96 / 111) | 0.846847 | **0.845** |
| MRR | 0.705405 | 0.687387 | **0.685** |

These replace hit@5 ≥ 0.85 and MRR ≥ 0.75, which no rule produced, and which were set on
a Golden Set that no longer exists. On the original 107 cases BM25 still clears both
(hit@5 0.885, MRR 0.757). The 24 cases added since are what pull MRR to 0.705: Golden Set
growth alone, on the old Corpus, already took it to 0.742. That is a change of instrument,
not a regression of the system, and the old gate could not tell the two apart.

The record carries the rule, its inputs, the Floors, the commit they were measured at and
a fingerprint of the Golden Set, so the arithmetic above can be redone from it.

### Recalibration

The Floors are re-derived only when what measures retrieval changes: a case added or
removed, or a question, Relevant Phrase or `answerable` edited. A Corpus, chunking or
retrieval-code change never moves them; those are what the gate exists to judge. The
re-derivation happens in the same change that caused it, by one command:

```bash
cd backend && uv run --frozen python eval/recalibrate.py retrieval
```

It measures the shipped arm over the full set, applies the rule and rewrites the record.
Nothing else writes it, and a test fails if a Floor no longer follows from the inputs
beside it.

The record's **fingerprint** is a hash over each case's question, Relevant Phrases and
`answerable`, sorted by case id. Nothing else a case carries can move a retrieval metric, so
a Required Fact edit never stales these Floors. When the committed Golden Set no longer
matches it, `--check` fails first, with **"Floors stale: Recalibrate"**, and compares no
metric at all, so a stale record is never mistaken for a regression. The ordinary test
suite runs the same comparison (`tests/test_recalibration.py`), so a Golden Set edit
without a Recalibration fails on its PR before any eval job runs.

**Only the shipped arm is gated**, and the gate looks it up with `shipped_arm_id()` rather
than naming it, so the gate follows production when the shipped arm changes. A Floor exists
to stop a change degrading what a visitor is actually served, and nothing is served by an
arm production does not run. The ungated arms are still measured, still published, and
still compared — they are just not build-breaking.

## What the harness has caught

The first two were in code that looked perfectly reasonable, and neither was visible to any
test. The third was not a bug at all — it was the architecture. The fourth was empirical bias
in the evaluation set itself. The fifth measured a change to the Corpus itself. The sixth
checked that a change of runtime is not a change of model. They are summarised on the
project page; the full accounts are here.

### ONNX Runtime reproduces the torch models; it does not run them as fast

The Candidate Arms swap torch for ONNX Runtime. Before any of them is compared with a
different model, the parity check asks whether the runtime alone changes anything. It runs
the ONNX export of the current embedding model against the torch version on the 68
development questions (158 Chunks):

| Comparison | Result |
|------------|--------|
| `onnx-dense` vs `dense`, per question | identical on all four metrics for 68 of 68 questions |
| `onnx-hybrid` vs `hybrid`, per question | identical on all four metrics for 68 of 68 questions |
| Corpus embeddings, ONNX vs torch | lowest cosine similarity 0.9999999; largest element difference 1.9e-7 |
| Cross-encoder logits, ONNX vs torch (40 pairs) | largest difference 7.6e-6; identical ordering |

So a difference between a later ONNX arm and `dense` comes from the model, not the
runtime. Adding the three arms also left the five existing ones unchanged: their per-question
results over all 111 questions were identical before and after.

The runtime does change the cost. `onnx-dense` answers in the same `~10ms` warm band as
`dense` (p95 15ms vs 11ms) but loads in `~1s` rather than `~100ms`, because creating the
ONNX session for a 438MB fp32 graph takes ~0.7s. `bm25+onnx-rerank-20` measured a warm p95
of 470–590ms, in the `~1s` band, against `~10ms` for `bm25+rerank`. Twice the pairs
explains 2×. The rest is ONNX Runtime running this cross-encoder 5–9× slower than torch on
the 16-core development machine. The optimized (`O3`) and quantized (`quint8_avx2`)
exports and several thread counts were tried, and none scored 20 pairs in under ~230ms.
These timings came from a machine shared with other jobs. The published bands come from the
CI run. As built, this arm is outside ADR-0009's `~100ms` warm limit. On held-out it won 3
questions and lost 1 against `bm25`, which is indistinguishable.

### Chunks cut along source structure moved no Arm beyond noise

The index build packed paragraphs into ~1,000-character windows with an overlap, so one
Chunk held several unrelated question-and-answer pairs and others were split across two.
"Where is David based?" missed even though its answer chunk contained the question. The
Corpus is now cut along each source's structure — one Chunk per question-and-answer pair,
per project section and per resume role, each headed with what it is about
([ADR-0011](adr/0011-structure-aware-chunking.md)). That took the Corpus from 123 to 157
Chunks.

Measured on the 54 development questions, before and after:

| Arm | hit@5 | MRR | recall@5 | Questions won / lost |
|-----|------:|----:|---------:|---------------------:|
| `bm25` (shipped) | 0.852 → 0.907 | 0.762 → 0.753 | 0.534 → 0.566 | 4 / 1 |
| `dense` | 0.741 → 0.796 | 0.581 → 0.698 | 0.388 → 0.439 | 5 / 2 |
| `hybrid` | 0.889 → 0.852 | 0.644 → 0.724 | 0.497 → 0.496 | 1 / 3 |
| `rerank` | 0.870 → 0.852 | 0.774 → 0.773 | 0.503 → 0.543 | 2 / 3 |
| `bm25+rerank` | 0.889 → 0.833 | 0.797 → 0.757 | 0.490 → 0.507 | 2 / 5 |

"Won / lost" counts the questions each Arm hit only after, or only before, re-chunking. No
Arm moved beyond sampling noise: the most lopsided split, BM25's 4 to 1, has an exact
two-sided sign test p of 0.375. Keyword search gained `location`, `paraphrase-undergrad-field`,
`paraphrase-philosophical-corpus` and `conceptual-production-regression-defense`, and lost
`predictive-maintenance`, whose answer is now one of three pieces of a long resume role.

**BM25's remaining misses.** The spec deferred any tokenizer change until re-chunking, and
then only for misses that survive it. Five did, and none is a tokenizer problem:

| Case | What the question says | What the Corpus says | First relevant rank |
|------|------------------------|----------------------|--------------------:|
| `education` | "study in college" | "Major: Biochemistry", "graduated" | 14 |
| `predictive-maintenance` | "predict equipment failure" | "predicts when parts will fail" | 26 |
| `paraphrase-security-clearance` | "national defense vetting" | "security clearance" | 14 |
| `conceptual-pipeline-simplification` | "discard complex machine learning stages" | "lost to plain keyword search" | 52 |
| `conceptual-query-context-alignment` | "genuinely grounding context" | "relevant context rather than relying on" | 21 |

Each is a vocabulary gap that no stemmer bridges. The only stemming mismatch,
`failure`/`fail`, lifts the `predictive-maintenance` answer only to rank 6 when conflated.
So the tokenizer was left alone. These are the questions the semantic Arms exist for.

The Floors were re-checked, not edited. Over the Golden Set as it then stood, BM25 went
from hit@5 0.862 to 0.885 and MRR 0.786 to 0.752, against the then Floors of 0.85 and 0.75.
A Corpus change is never a reason to move a Floor. The Golden Set has since grown, and
the Floors were re-derived by rule for it: see [How the Floors are derived](#how-the-floors-are-derived).

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
`holdout` only — see [Splits](#method). The published sample is 43 questions, which is
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
`build_messages` and samples with the `TEMPERATURE` (0) and `MAX_TOKENS` production used
while it served Groq. Production generated at temperature 0 for the same reason
([ADR-0007](adr/0007-generation-evaluation-harness.md)): the eval should measure what
visitors are served. Production now serves OpenAI (#73), which accepts no temperature;
the OpenAI generator shares production's prompt, model, reasoning effort and completion
cap instead, and a test asserts it sends exactly what `/api/chat` sends.

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

It also takes a worker count, default 1: how many cases are answered and judged at once.
Each case spends nearly all its time waiting on OpenAI and Jev, so the entry scripts
(the gate, the comparison run, `judge_generation.py` and an OpenAI `run_generation.py`
record) take `--workers`, default 8. Workers only produce results. Each result is handed
to the per-case callback on the calling thread as it finishes, so a run that stops partway
still keeps every answer already paid for, and the run lists its cases in Golden Set order
whatever order they finished in. The first error starts no further case; cases already
under way are finished and kept, then the error is raised. The Judge's and the splitter's
billed-usage totals are updated under a lock, and the retriever answers one query before
the workers start, so a model it loads on first use is loaded once. The Groq baseline is
always answered one case at a time: its pacing assumes a single caller.

TypeSafe publishes no numeric rate limits, only that a 429 (rate limited) or 529
(overloaded) should be retried with exponential backoff. Eight workers limited together
would retry together and be limited again, so before each of its five retries the Judge
waits 1, 2, 4, 8 and then 16 seconds, plus up to as much again at random. A `Retry-After`
the response carries, in seconds or as a date, replaces that base when it is longer, so
the server's wait is never cut short and is still jittered. Each retry is counted,
under the same lock as the billed tokens, and the Judge's usage is reported as
`{input_tokens, output_tokens, retries}`: a run slowed by rate limits shows a retry count
rather than only a long wall-clock time.

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
| Claims | the question and one sentence | the sentence's standalone claims |
| Relation | one claim and one retrieved chunk | supports / contradicts / says nothing |
| Conveys | the whole answer and one Required Fact | yes / no |

Per case, the answer is first asked whether it Declines. A Decline, and any answer to
an Out-of-Scope Case, is judged no further: the Judge is weak on negation, so "the
information doesn't include that" would otherwise count as an unsupported claim. Every
other answer is split into sentences in code, and filler is dropped. A sentence counts
as filler only when Jev is confident it is (P(factual) < 0.2): a factual sentence dropped
is never checked, which flatters Faithfulness.

Each factual sentence is then split into standalone claims, and each claim is judged
against each retrieved chunk separately. A sentence is supported only if every one of
its claims is. Different chunks may support different claims, and a chunk supports a
claim when Jev finds `supports` more likely than not (P ≥ 0.5). Jev returns judgments,
not text, so the splitting is done by OpenAI's `gpt-6-luna` (`eval/splitter.py`), given
the question so that "it" and "the system" can be resolved. Judging whole compound
sentences let one chunk that backed part of a sentence pass all of it ([Validating the
Judge](#validating-the-judge), [ADR-0007](adr/0007-generation-evaluation-harness.md)). A
judged run records the splitter's model and usage next to the Judge version, and each
sentence's claims.

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

This needs `JEV_API_KEY`, and `OPENAI_CI_API_KEY` for the splitter. The CLI prints the
metrics and then each Contradiction with its case, sentence, claim and chunk. `--output`
writes the same, plus per-case judgments, the Judge version, the splitter's model, both
billed usages (the Judge's with its retry count) and the judged record's provenance, as
JSON. Judging a
stored record publishes nothing and gates nothing; the [generation
gate](#generation-gate-and-published-results) does both.

## Validating the Judge

Before a Judge result gates anything, its verdicts are compared with hand labels
([ADR-0007](adr/0007-generation-evaluation-harness.md)). `backend/eval/judge_validation.json`
holds 32 sentences from the Groq baseline's answers, each labelled against the chunks its
answer was written from, plus 12 held-out sentences (below):

| Label | Meaning |
|---|---|
| filler | states nothing about David: a pleasantry, heading, transition, or a remark about the context |
| supported | every claim in it is stated or clearly implied by the chunks, together if not by one |
| contradicted | a chunk states the opposite of a claim in it |
| says nothing | neither: at least one claim has no basis in the chunks, and none is contradicted |

Each sentence is also marked compound (several claims) or single. 23 of the 32 are
compound on purpose: if Jev's disagreements cluster there, that is the case for an LLM
step that splits answers into atomic claims. They did, and that step was adopted (#81,
ADR-0007 amendment, and the result below). A test fails if
a labelled sentence is no longer one the harness's splitter produces from its stored
answer, so the labels cannot quietly drift away from what is judged.

`eval/validate_judge.py` runs the labelled sentences through the harness's own sentence
judgment (filler, then claims, then each claim against each chunk) and reports two
agreements, one per thing a judged run outputs:

- **Faithfulness agreement**: filler, supported or unsupported, where contradicted and
  says-nothing both count as unsupported;
- **Contradiction agreement**: whether a Contradiction is listed for the sentence.

It then lists every disagreement with its claims and Jev's per-chunk relations for each,
and counts disagreements
separately for compound and single sentences.

```bash
cd backend
uv run --frozen python eval/validate_judge.py --output validation-run.json          # tuning
uv run --frozen python eval/validate_judge.py --final --output validation-run.json  # final
```

The labels were drafted before any of Jev's judgments of these sentences were looked at,
then reviewed by David. The CLI refuses to measure against labels whose `status` is not
`reviewed` (`--draft` overrides).

### Held-out sentences

Fixing the Judge's questions (#81) means tuning their wording against the 32 labels
above, which would make agreement on those 32 look better than it is. So the set also
holds 12 **held-out** sentences (`"heldOut": true`), written by hand rather than taken
from an answer. Each is unsupported by its case's chunks: 5 contradicted and 7 saying
nothing. Their labels were written before Jev judged any of them, and David reviewed them.
They are built to test both known causes without repeating the tuned sentences: 6 don't
name David, 6 are partly supported, 7 are compound and 5 single, and two name a different
item of the same kind as a chunk (a different embedding model, a different forecasting
model) without contradicting it.

A tuning run leaves them out. Only `--final` judges them, so tuning never sees Jev's
judgments of them. The five supported sentences that no single chunk supports, only
several together, are marked `"acrossChunks": true`.

### The pass bar

David set this bar before the final run. Faithfulness may gate (#71) only once the
final measurement meets every line. The final measurement is three `--final` runs, each
line checked against the median of the three. Claim splits and Jev's borderline judgments
vary from run to run, so one run could pass or fail on noise. David chose this protocol
before the final run too.

| Measure | Bar | Over |
|---|---|---|
| Unsupported sentences caught | **≥ 83%** | held-out unsupported sentences Jev calls unsupported |
| Supported sentences kept | ≥ 90% | supported sentences Jev still calls supported |
| Supported across chunks kept | ≥ 80% | of those, the ones only several chunks together support |
| Faithfulness agreement | ≥ 85% | every labelled sentence, held-out included |

The bar is in shares, not counts, so it still applies as the set grows. Caught counts
only held-out sentences, because the others were tuned against. At 12 sentences, 83%
means 10 caught: the fewest that shows, at 95% confidence (Wilson interval), that Jev
catches more than half of unsupported sentences. The two "kept" lines guard against the
easy fix of calling more sentences unsupported. The across-chunks line covers the
sentences a strict `supports`, asked one chunk at a time, would fail. Contradictions
are reported but have no bar, since they are not gated. `--final` prints each measure for
each run and its median against the bar, and exits non-zero if any median misses.

### Result: Jev is not yet fit to gate Faithfulness

Measured 2026-10-10 with `jev-1.13.0` at `14ba262`, with the questions as they were then.
They have since been fixed, and the result is [below](#result-jev-meets-the-bar).

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

### Fixing the questions (#81)

The questions were tuned against the 32 labels above only. Jev judged no held-out
sentence until the questions were frozen. Each step below was measured on the 32:

| Approach | Supported kept | Across chunks kept | Unsupported caught |
|---|---|---|---|
| Before (#70) | 21 of 22 | 5 of 5 | 0 of 7 |
| Strict `supports`, whole sentence, one chunk at a time | 18 of 22 | 1 of 5 | 1 of 7 |
| One strict question over the sentence and all its chunks | no threshold meets the bar | | |
| Hand-split claims, each against each chunk | 22 of 22 | 5 of 5 | 5 of 7 |
| `gpt-6-luna` claims, each against each chunk (three runs) | 22, 20, 22 | 5, 5, 5 | 5, 7, 7 |

- **Filler.** The question now asks for any checkable statement about David *or his
  projects, systems and results*, named or not. On the 32, real filler then scored at
  most 0.08 and every factual sentence at least 0.73. A sentence is dropped only below
  0.2, because dropping a factual one is the costlier error.
- **Partly supported sentences.** A strict `supports` (every part) asked one chunk at a
  time fixed nothing it didn't also break: the sentences whose parts different chunks
  back failed, and Jev still passed most partly supported ones. Asked once with all five
  chunks, its scores for supported and unsupported sentences overlapped across
  0.56–0.79. Splitting into claims was first tried with claims written by hand, as an
  upper bound, and then with `gpt-6-luna`'s, and handled both kinds. The strict wording
  is kept for claims, since the splitter sometimes leaves a list whole.
- **Support threshold.** A claim is supported when Jev finds `supports` more likely than
  not. Over three runs, 0.6 and 0.7 cost more supported sentences than they caught
  unsupported ones.
- **Contradictions.** The narrowed wording did not stop Jev listing a chunk that names a
  different item of the same kind (another CI tool, another certificate). With every
  claim judged against every chunk there are more pairs to list, and Contradiction
  agreement on the 32 fell to 0.84–0.88. Contradictions are listed for review, not gated.
- **Run-to-run noise.** Luna's splits and Jev's borderline probabilities both vary between
  runs. Most of the spread above comes from a few sentences near the line: the diamonds
  sentence scores 0.50–0.53, and an over-split such as "other DoD-approved LLMs besides…",
  from "among others", can fail a supported sentence.

### Result: Jev meets the bar

Measured 2026-10-11 at `72d2df9`, with the questions frozen beforehand: `jev-1.13.0`,
claims split by `gpt-6-luna`, three `--final` runs over all 44 labelled sentences. It was
the first time Jev judged the held-out sentences.

| Measure | Runs | Median | Bar | |
|---|---|---|---|---|
| Unsupported caught (held-out) | 1.000, 1.000, 1.000 | **1.000** | ≥ 83% | met |
| Supported kept | 1.000, 1.000, 0.955 | **1.000** | ≥ 90% | met |
| Supported across chunks kept | 1.000, 1.000, 1.000 | **1.000** | ≥ 80% | met |
| Faithfulness agreement | 0.977, 0.955, 0.955 | **0.955** | ≥ 85% | met |
| Contradiction agreement (no bar) | 0.864, 0.909, 0.909 | 0.909 | — | |

Jev's Faithfulness verdict against the hand labels, summed over the three runs (each
sentence counted once per run):

| Hand label | Jev: filler | Jev: supported | Jev: unsupported |
|---|---|---|---|
| filler (3 × 3) | 9 | 0 | 0 |
| supported (22 × 3) | 0 | 65 | 1 |
| unsupported, tuned (7 × 3) | 0 | **4** | 17 |
| unsupported, held-out (12 × 3: 5 contradicted, 7 says nothing) | 0 | **0** | **36** |

Before the fix, Jev called 0 of 7 unsupported sentences unsupported. Now it catches every
held-out one in every run, and 17 of 21 tuned ones. Every remaining Faithfulness error
on an unsupported sentence is the same kind: a chunk about a *similar* system taken as
support. "Each [Nietzsche] deployment includes an automated evaluation pipeline" passes on
the portfolio chatbot's evaluation, every run. The one supported sentence lost (run 3) is
the borderline diamonds sentence.

What this does and does not show:

- **Held-out covers unsupported sentences only.** "Supported kept" is measured on the
  tuned sentences, so false alarms on unseen supported sentences are untested here.
- **Contradictions are still noisy.** The narrowed `contradicts` did not stop Jev
  listing a chunk that names a different item of the same kind: held-out sentence 10
  (OpenAI embeddings, where the chunk names Titan) is listed as contradicted in every run,
  and some supported sentences are too. All five contradicted held-out sentences were
  listed. The other different-item sentence (LightGBM's skill, where the chunk gives
  ARIMA's) was not. Contradictions remain listed for review, not gated.
- **Twelve sentences is a small sample.** 36 of 36 across three runs is strong evidence
  that Jev now catches most unsupported sentences of these kinds. It doesn't pin down the
  rate.

Faithfulness may now gate (#71), at the Floor that the rerun of the run-to-run spread below
sets with these questions.

### Validating the Decline judgment

Decline accuracy gates too, and it rests on a different Judge question: whether the whole
answer Declines (`DECLINES_QUESTION` in `backend/eval/judge.py`). The sentence labels
above never test it. In the generation gate's first CI run it counted a partial answer as
a Decline: `paraphrase-series-stationarity` names the ADF and KPSS tests, then says
separate procedures aren't specified. Per [`CONTEXT.md`](../CONTEXT.md), an answer that
gives part of what was asked is not a Decline.

So `judge_validation.json` also holds **answer-level Decline labels** under `declines`. Each
label has the case, the question and answer exactly as judged, and whether the answer
Declines. It also says which stored run the answer came from (`declineRuns`: the gate's
first CI run, and the Shipped Arm's answers in the comparison run of Candidate Arms) and
what kind of answer it is:

| Kind | Labels | What it is |
|---|---|---|
| `decline` | 10 | says the information isn't available and gives nothing else; 3 are on answerable cases, where the Decline is wrong but still a Decline |
| `answer` | 10 | answers directly, including answers that begin "No." |
| `hedged` | 11 | says something isn't available and also gives something: part of what was asked (6, not a Decline) or only something near it (5, a Decline) |

The hedged third is where Jev has already been wrong. Two labels are on the same case
(`conceptual-statistical-evaluation-rigor`): one answer lists safeguards first, and the
other says the safeguards aren't described.

A label is held out when its Golden Set case is: the Split rule already in use, so 17 of
the 31 are held out. As with sentences, a tuning run leaves held-out labels out. The labels
were drafted from the answers' text without Jev's verdicts in view, and stayed marked
`"draft": true` until David reviewed them (all 31 kept as drafted). A label marked draft
is never measured against unless `--draft` is passed.

```bash
cd backend
uv run --frozen python eval/validate_judge.py --declines --draft                 # tuning, against drafts
uv run --frozen python eval/validate_judge.py --declines --final --output declines-run.json  # final
```

The report gives agreement over every label measured and over held-out labels alone. It
counts disagreements per kind and lists each one with its question and answer.

**Pass bar.** Decline accuracy may gate only once the final measurement reaches
**≥ 0.9 agreement on held-out labels**, as the median of three `--final` runs
(`DECLINE_PASS_BAR`). The protocol is the one used for sentences. With 17 held-out labels,
that allows one disagreement (16 of 17 is 0.94; 15 of 17 is 0.88).

### Result: the Decline judgment meets the bar

Measured 2026-10-12 at `42f0e78`, with `DECLINES_QUESTION` unchanged since the gate's first
CI run: `jev-1.13.0`, three `--final` runs over all 31 reviewed labels. It was the first
time Jev judged the held-out labels. The question was not reworded, so the run-to-run
spread below still holds for this instrument.

| Measure | Runs | Median | Bar | |
|---|---|---|---|---|
| Held-out Decline agreement (17 labels) | 1.000, 1.000, 1.000 | **1.000** | ≥ 0.9 | met |
| Decline agreement, all 31 (no bar) | 0.968, 0.968, 0.968 | 0.968 | — | |

| Kind | Labels (held-out) | Disagreements per run |
|---|---|---|
| `decline` | 10 (5) | 0 |
| `answer` | 10 (5) | 0 |
| `hedged` | 11 (7) | 1 |

The one disagreement is the same in every run, and it is the answer that prompted this
validation: `paraphrase-series-stationarity` (dev, gate run). It names the ADF and KPSS
tests, then says separate procedures for constant mean and variance aren't specified. The
hand label says it answers in part. Jev says it Declines. The other five partial answers
and all five Declines with nearby context were judged as labelled.

What this does and does not show:

- **The known error remains.** Jev still reads a partial answer that ends by naming what
  is missing as a Decline. This case is answerable, so in the gate it counts against
  Decline accuracy when it shouldn't. Held-out has 4 partial answers and Jev got all of
  them right, so the error isn't systematic, but it isn't fixed either.
- **Seventeen labels is a small sample.** 51 of 51 held-out judgments across three runs
  shows Jev agrees with the labels on answers like these. It doesn't pin down the rate.
- **Jev's verdicts here didn't vary.** Every label got the same verdict in all three runs.

Decline accuracy may gate, at the Floor that the run-to-run spread below sets.

## Run-to-run spread

The same commit does not give the same numbers twice: Jev is not fully deterministic, and
OpenAI's reasoning models, which also split sentences into claims, generate only at the
default temperature. The spread of five judged runs sets two things
([ADR-0007](adr/0007-generation-evaluation-harness.md),
[ADR-0012](adr/0012-recalibration.md)):

- each published generation metric's **rounding step**, from its own held-out spread
  (held-out is what is published): the smallest of 0.005 / 0.01 / 0.02 / 0.05 / 0.1 no
  smaller than that metric's range;
- the **Floors** for Faithfulness and Decline accuracy, from the spread over every case
  (the gate runs on the full Golden Set): the lowest run minus twice the range (a handful
  of runs understates the noise), and at least one of the metric's steps, rounded down to
  its step.

Until #81 one step, set by the noisiest metric, applied to every metric. Fact Recall moves
with every reworded answer, and once its range reached 0.08 that rule set a step of 0.1
and both Floors at 0.80, which would fire only on a collapse. David chose a step per
metric (ADR-0007, amendment of 2026-10-11). Three runs then understated the noise, so the
study is now five (#90).

### The five-run study (2026-10-11, #91)

Five generations of the Shipped Arm, `bm25`, with `gpt-6-luna` at reasoning effort `low`
over all 131 cases (111 answerable, 20 Out-of-Scope; 49 held-out) and 158 Corpus Chunks,
each judged once at `6dead1d` by `jev-1.13.0` with the validated Judge questions, claims
split by `gpt-6-luna` at effort `low`, filler cutoff 0.2. Two of the five reuse answers
already paid for, re-judged: the first CI gate run on 131 cases (Actions run 38184969261)
and the Shipped Arm of the comparison run, both generated at `0e8b406`. The other three
were generated at `6dead1d`. Nothing between the two commits changes an answer.

| Metric | Held-out | Range | All cases | Range |
|---|---|---|---|---|
| Fact Recall | 0.652, 0.634, 0.643, 0.652, 0.634 | 0.018 | 0.697, 0.682, 0.701, 0.689, 0.689 | 0.019 |
| Faithfulness | 0.960, 0.952, 0.934, 0.974, 0.987 | 0.053 | 0.954, 0.948, 0.956, 0.972, 0.946 | 0.026 |
| Decline accuracy | 0.898, 0.918, 0.898, 0.898, 0.898 | 0.020 | 0.901, 0.916, 0.908, 0.901, 0.908 | 0.015 |

Only 5 of the 131 answers were word-for-word the same in all five runs. Held-out Fact
Recall is 71 to 73 of 112 Required Facts. Held-out Faithfulness is 1 to 5 unsupported
sentences in ~77, so a couple of sentences near the line move it by 0.05. Decline accuracy
is not noise: every wrong Decline in every run is an answerable question the model
declined (no Out-of-Scope question was ever answered), and 11 of those questions were
declined in all five runs. They are misses the gate measures, not spread.

Derived by `eval/recalibrate.py generation`:

| | Value | Derivation |
|---|---|---|
| Rounding step, Fact Recall | **0.02** | smallest step ≥ 0.018 |
| Rounding step, Faithfulness | **0.1** | smallest step ≥ 0.053 |
| Rounding step, Decline accuracy | **0.05** | smallest step ≥ 0.020 |
| Faithfulness Floor | **0.80** | 0.946 − max(2 × 0.026, 0.1) = 0.846, rounded down to 0.80 |
| Decline accuracy Floor | **0.85** | 0.901 − max(2 × 0.015, 0.05) = 0.851, rounded down to 0.85 |

These replace the three-run Floors of 0.85 and 0.915, measured on the 107-case Golden Set.
Faithfulness's held-out range, just over 0.05, now sets its step at 0.1 and so its Floor at
0.80, the outcome the per-metric step was meant to avoid; this time it comes from
Faithfulness's own spread, not Fact Recall's. Decline accuracy's lower Floor reflects the
new Golden Set's harder questions, which the model declines more often.

**Judge only (earlier study).** On 2026-10-11, with the questions fixed in #81, one Luna
record of the 107-case Golden Set was judged three times at `b2f4889`: all three
metrics had a range of 0. The three judgings split 86 of the 167 factual sentences into
different claims, and only 2 sentence verdicts changed, in opposite directions. Judging is
not the noise; generation is.

### The generation Floors record

The steps and Floors live in one committed record, `backend/eval/floors/generation.json`,
and nowhere in code: the gate reads its Floors from it and the publisher its steps
([ADR-0012](adr/0012-recalibration.md)). The record holds the rule, its inputs (every
run's values and range, held-out and over all cases), the steps, the Floors, a fingerprint
and the commit the runs were judged at, and a test fails if a step or Floor no longer
follows from the inputs beside it.

The fingerprint covers what can move a generation metric: each case's question, Required
Facts and `answerable`, sorted by case id, plus the instrument: the Judge version, the
wording of every Judge question, the Judge's filler cutoff (`FACTUAL_BELOW`), the splitter
model and its reasoning effort, and the generation model and reasoning effort. The cutoff
and the splitter's effort decide which sentences count and what claims get judged, so
changing either is a new instrument too. Relevant Phrases are left out, so a retrieval label repair never forces
a paid study, and the retrieval fingerprint leaves out Required Facts and the instrument.

A change to any of these is a Recalibration, in the same change: five generations of the
Shipped Arm, each judged, then the recalibrate command, the only writer of the record. It
is built for five runs and refuses any other number, or a run that skipped a case:

```bash
cd backend
uv run --frozen python eval/run_generation.py --provider openai --record runs/luna-1.json
uv run --frozen python eval/judge_generation.py --record runs/luna-1.json --output runs/judged-1.json
# ... five of each, then:
uv run --frozen python eval/recalibrate.py generation runs/judged-{1,2,3,4,5}.json
```

The record was first carried over by hand from the three-run study's constants on the
107-case Golden Set, with no fingerprint, so it was stale and the gate failed "Floors
stale: Recalibrate" until the five-run study above recalibrated it (#91). The ordinary
test suite checks the committed record against the committed Golden Set and instrument
(`tests/test_recalibration.py`), so a change that stales it fails there first, for free.

`--provider openai` sends no temperature (the candidates reject any but the default) and
pins `--reasoning-effort` (default `low`). It needs `OPENAI_CI_API_KEY` and a `--record`
path, so it cannot overwrite the Groq baseline. A Luna run of all 131 cases bills ~92k
tokens and takes under a minute, eight cases at a time. Judging one bills Jev ~2.05–2.15M
input tokens (each sentence becomes ~3 claims, each judged against 5 chunks) and the
splitter ~82–86k tokens, and takes about two minutes.

## Generation gate and published results

`eval/gate_generation.py` answers every Golden Set case (both Splits) with the Shipped
Arm and `gpt-6-luna` at reasoning effort `low`, the model the Floors were measured on,
and judges every answer. It fails if Faithfulness or Decline accuracy over the whole set
falls below its Floor in the [generation Floors record](#the-generation-floors-record).
Before any of that, it checks the record's fingerprint against the Golden Set and the
instrument, and on a mismatch fails first with **"Floors stale: Recalibrate"**, generating
and judging nothing. A gated metric with nothing to measure fails too. Fact Recall and Contradictions are printed but not gated
([ADR-0007](adr/0007-generation-evaluation-harness.md)).

The gate generates with the model production serves by default: `eval/run_generation.py`
takes its model and reasoning effort from `app.config.DEFAULT_OPENAI_MODEL` and
`app.llm.REASONING_EFFORT`, and a test asserts the gate's request matches the chat
endpoint's. An `OPENAI_MODEL` override in Railway is not measured by the gate.

CI runs it from `.github/workflows/generation-gate.yml`, on pull requests and pushes to
`main` that touch what can change an answer: the prompt and model configuration
(`app/llm.py`, `app/config.py`), retrieval code and indexes, the Corpus sources, the
Golden Set, and the generation harness. Dependency bumps don't trigger it, so they spend
no API budget. It uses CI's own keys (`OPENAI_CI_API_KEY`, and `JEV_CI_API_KEY` passed as
`JEV_API_KEY`), never production's. It answers and judges eight cases at a time
(`--workers`), so the gate step takes about two and a half minutes in CI (2m11s–2m27s
measured on 131 cases), not the ~20 it took one case at a time, and costs a few cents: the
same calls, made concurrently. The job's timeout is 10 minutes, room for Jev's retries.
The judged run is uploaded as the `generation-run` artifact.

On `main`, a passing run publishes its **held-out** cases as the Shipped Arm section of
`frontend/data/generationResults.json` (`eval/publish_generation.py`), which the portfolio
page renders. A run below a Floor publishes nothing. The document has two sections, each
with its own provenance (commit, CI run link, time), because they come from different
runs: `shippedArm` from this gate, and `comparison` from the manual comparison run of
Candidate Arms. A run replaces only its own section.

| Published field | Measured? | |
|---|---|---|
| Fact Recall, Faithfulness, Decline accuracy | yes | rounded to each metric's step: 0.02, 0.1, 0.05 |
| cost per answer (USD) | yes | mean billed usage at OpenAI's list prices, to one significant figure |
| generation model ID, reasoning effort | yes | the model ID OpenAI reports answering with |
| Judge version, splitter model | yes | |
| Arm, Corpus size, split, question counts, steps | yes | |
| commit, CI run URL, time | no | provenance |

A section is rewritten only when a measured field changes, so a rerun whose rounded
numbers match commits nothing: noise alone never produces a results commit. A change of
generation model or Judge version is a new measurement even if every number matches. As
for retrieval, a CI run replaces a local run's provenance once.

Cost per answer uses OpenAI's standard prices from 2026-10-11 (`PRICES_PER_MILLION`:
Luna $0.10 in / $0.50 out per million tokens; reasoning tokens bill as output). Cached
input is cheaper, so it is an upper bound. A model with no recorded price is refused
rather than published without a cost.

```bash
make generation-gate                              # gate only; needs backend/.env keys
PUBLISH_EVAL=1 ./scripts/backend-generation-gate.sh   # gate, then publish if it passes
```

## Choosing the generation model

Generation moves from Groq to OpenAI by [ADR-0008](adr/0008-generation-moves-to-openai.md)'s
rule: `gpt-6-luna` replaces Groq unless it is distinguishably worse on Faithfulness or
Decline accuracy, and `gpt-6.1-sol` (about 20× the price) replaces Luna only if it is
distinguishably better on either. Fact Recall breaks ties only. "Distinguishably" is
[ADR-0006](adr/0006-noise-aware-verdict-line.md)'s exact sign test at p < 0.05, run on the
pairs where two models disagree:

- **Faithfulness**, per case: faithful when every factual sentence of the answer is
  supported. Cases that either model declined, and Out-of-Scope Cases, are left out.
- **Decline accuracy**, per case: correct or not.
- **Fact Recall**, per Required Fact.

The pairing choices are recorded in the ADR-0008 amendment. The decision is made on `dev`
and confirmed on `holdout`.

Luna and Sol answered the 107 cases the Groq baseline holds from the chunks stored in it,
not from retrieval over today's Corpus, so the model is the only variable. These were the
whole Golden Set when the baseline was captured. The 24 cases added since were not
measured here, and none of the 107 changed. Each ran once,
with reasoning effort `low` and no temperature (ADR-0007 amendment). All three records
were judged on 2026-10-11 by `jev-1.13.0`, with claims split by `gpt-6-luna`, using the
judging code of `94a7b95` (the same as the [run-to-run spread](#run-to-run-spread)).

| | Fact Recall | Faithfulness | Decline accuracy | Unsupported / factual sentences | Cost per answer |
|---|---|---|---|---|---|
| **`dev`** (68 cases) | | | | | |
| Groq `openai/gpt-oss-120b` | 0.754 | 0.758 | 0.912 | 37 / 153 | $0 (free tier) |
| `gpt-6-luna` | 0.720 | **0.981** | 0.912 | 2 / 106 | $0.00012 |
| `gpt-6.1-sol` | 0.780 | 0.945 | 0.926 | 9 / 163 | $0.0027 |
| **`holdout`** (39 cases) | | | | | |
| Groq `openai/gpt-oss-120b` | 0.736 | 0.762 | 1.000 | 25 / 105 | $0 (free tier) |
| `gpt-6-luna` | 0.701 | **0.986** | 1.000 | 1 / 70 | $0.00012 |
| `gpt-6.1-sol` | 0.782 | 0.963 | 1.000 | 4 / 107 | $0.0028 |

Pairs won and lost, with the sign test's outcome:

| Comparison | Split | Faithfulness | Decline accuracy | Fact Recall |
|---|---|---|---|---|
| Luna vs Groq | `dev` | 15–0 **ahead** | 0–0 | 3–7 |
| Luna vs Groq | `holdout` | 10–0 **ahead** | 0–0 | 3–6 |
| Sol vs Luna | `dev` | 1–7 | 1–0 | 8–1 **ahead** |
| Sol vs Luna | `holdout` | 1–4 | 0–0 | 8–1 **ahead** |

**Result: `gpt-6-luna`.** On `dev`, Luna is not worse than Groq on either gated metric, so
it replaces Groq. It is distinguishably *more* faithful: Groq wrote an unsupported
sentence in 15 answers where Luna wrote none, and the reverse never happened. Sol is
indistinguishable from Luna on both gated metrics, so it does not replace Luna. Its
Fact Recall lead (8–1) is real, but by the rule it never justifies an upgrade alone.
`holdout` gives the same choice on every step.

What to keep in mind when reading this:

- **Length is not the explanation.** Over all cases, Groq's answers state 258 factual
  sentences, Luna's 176 and Sol's 270. Sol says as much as Groq and leaves 13 unsupported
  where Groq leaves 62. Luna's answers are the shortest, which fits its lowest Fact
  Recall.
- **The Judge was tuned on Groq's sentences.** The 32 tuned validation sentences
  ([Validating the Judge](#validating-the-judge)) came from Groq baseline answers. Jev may
  be better at catching Groq's kind of unsupported sentence. The held-out sentences were
  hand-written, not Groq's.
- **Luna splits its own answers into claims.** ADR-0007 accepts this self-preference risk:
  Jev, a different model, still judges every claim, and the held-out validation bar would
  show a splitter that smoothed claims into supportable ones.
- **Sol was nearly behind Luna on `dev` Faithfulness** (1–7, p = 0.07). Paying 22× more
  would not have bought fewer unsupported sentences.
- **Decline accuracy did not separate the models.** None answered an Out-of-Scope Case.
  The `dev` misses are 6 answerable cases (5 for Sol) declined because the stored
  contexts lacked the answer. Retrieval misses those, not the model.
- **Contradictions** (not gated) are 84 for Groq, 17 for Luna and 53 for Sol over all
  cases. As [noted above](#result-jev-meets-the-bar), Jev still lists chunks that name a
  different item of the same kind, so these counts need reading entry by entry.

Cost per answer is billed `usage` at OpenAI's standard list price on 2026-10-11 (Luna
$0.10 / $0.50, Sol $2.00 / $10.00 per 1M input / output tokens), with every input token
priced as uncached, an upper bound. Groq's free tier has no price, and its paid tier is
no longer offered. The run-to-run spread and Floors [above](#run-to-run-spread) were
already measured on Luna, so the choice needs no new spread study. Production has served
Luna since #73.

```bash
cd backend
uv run --frozen python eval/run_generation.py --provider openai --model gpt-6-luna \
    --contexts eval/baselines/groq.json --record runs/luna.json
uv run --frozen python eval/run_generation.py --provider openai --model gpt-6.1-sol \
    --contexts eval/baselines/groq.json --record runs/sol.json
uv run --frozen python eval/judge_generation.py --output runs/judged-groq.json
uv run --frozen python eval/judge_generation.py --record runs/luna.json --output runs/judged-luna.json
uv run --frozen python eval/judge_generation.py --record runs/sol.json --output runs/judged-sol.json
uv run --frozen python eval/select_model.py runs/judged-groq.json runs/judged-luna.json runs/judged-sol.json
```

`--contexts` answers from a stored record's chunks instead of retrieving, and records
the Arm and Corpus size those chunks came from. Replaying refuses a Golden Set case the
record never answered, so these commands reproduce the comparison only with the Golden Set
of `94a7b95`, before the cases the baseline lacks were added. The two generations billed 109k (Luna)
and 113k (Sol) tokens. Judging billed Jev 3.5M (Groq), 1.9M (Luna) and 3.1M (Sol) input
tokens, since longer answers have more claims to check.

## Comparing Candidate Arms through generation

The Shipped Arm is chosen by [ADR-0009](adr/0009-shipped-arm-selection-rule.md)'s rule,
which reads answers, not retrieval metrics: a Candidate Arm replaces BM25 only if it is
distinguishably better on Fact Recall, not distinguishably worse on Faithfulness or
Decline accuracy, and no slower than the `~100ms` Latency Band warm. `eval/compare_arms.py`
produces the evidence. Every Candidate Arm (`bm25`, `onnx-dense`, `onnx-hybrid`,
`bm25+onnx-rerank-20`; never a Reference Arm) retrieves for every Golden Set case on both
Splits, `gpt-6-luna` at reasoning effort `low` answers from what that Arm retrieved, and
the pinned Judge scores each answer. Only the Arm varies; each Arm's answers are generated
afresh, so run-to-run noise in the model adds to the disagreements the test sees.

Each Candidate Arm is compared with the Shipped Arm on the pairs where they disagree, by
the same exact sign test as for [choosing the generation model](#choosing-the-generation-model):
Faithfulness and Decline accuracy per case, Fact Recall per Required Fact. The run prints
the `dev` and `holdout` reports (metrics per Arm, then each Arm's won/lost and outcome per
metric). The rule is applied to `dev` and confirmed on `holdout`; the latency condition
is read from the retrieval Scoreboard's Latency Bands.

CI runs it from `.github/workflows/generation-comparison.yml`, only when dispatched by
hand: it costs about four generation gate runs, eight cases at a time within each Arm.
Every Arm's judged run on both Splits is
uploaded as the `comparison-run` artifact, which is where the `dev` results the decision
is made on live; they are never published. A run dispatched on `main` publishes the
**held-out** results as the `comparison` section of `frontend/data/generationResults.json`,
with its own provenance, and the portfolio page renders it under the Shipped Arm table. A
run on another branch publishes nothing.

| Comparison field | Measured? | |
|---|---|---|
| per Arm: Fact Recall, Faithfulness, Decline accuracy | yes | rounded to the same steps as the Shipped Arm section |
| per Arm: won/lost against the Shipped Arm and outcome, per metric | yes | `null` for the Shipped Arm itself |
| per Arm: cost per answer, eligibility, label | yes | |
| Shipped Arm, generation model ID, reasoning effort, Judge version, splitter model | yes | |
| Corpus size, split, question counts, steps | yes | |
| commit, CI run URL, time | no | provenance |

As for the Shipped Arm section, a rerun whose rounded numbers and outcomes all match
commits nothing.

```bash
make generation-comparison                                   # report only; needs backend/.env keys
COMPARISON_RUN_OUTPUT=runs/comparison.json make generation-comparison   # keep the judged runs
PUBLISH_EVAL=1 ./scripts/backend-generation-comparison.sh    # report, then publish holdout
```

### Result: no Candidate Arm qualifies; keyword search stays shipped

Measured 2026-10-11 at `6691b03`, on 158 Chunks: `gpt-6-luna` at reasoning effort `low`,
judged by `jev-1.13.0` with claims split by `gpt-6-luna`. It was run locally with CI's keys
(`COMPARISON_RUN_OUTPUT=… make generation-comparison`), because the workflow isn't on `main`
yet and so can't be dispatched. Nothing was published.

| | Fact Recall | Faithfulness | Decline accuracy | Warm Latency Band |
|---|---|---|---|---|
| **`dev`** (82 cases: 68 answerable, 152 Required Facts) | | | | |
| `bm25` (shipped) | 0.717 | 0.946 | 0.915 | `~1ms` |
| `onnx-dense` | 0.697 | 0.967 | 0.854 | `~10ms` |
| `onnx-hybrid` | 0.750 | 0.952 | 0.902 | `~10ms` |
| `bm25+onnx-rerank-20` | 0.743 | 0.961 | 0.927 | `~1s` |
| **`holdout`** (49 cases: 43 answerable, 112 Required Facts) | | | | |
| `bm25` (shipped) | 0.643 | 0.928 | 0.918 | |
| `onnx-dense` | 0.598 | 0.972 | 0.878 | |
| `onnx-hybrid` | 0.670 | 0.943 | 0.980 | |
| `bm25+onnx-rerank-20` | 0.714 | 0.944 | 0.959 | |

Won–lost against `bm25`, with the exact sign test's two-sided p. Every comparison is
indistinguishable at p < 0.05:

| Arm | Split | Fact Recall | Faithfulness | Decline accuracy |
|---|---|---|---|---|
| `onnx-dense` | `dev` | 20–23 (p 0.76) | 4–3 | 4–9 (p 0.27) |
| `onnx-hybrid` | `dev` | 20–15 (p 0.50) | 4–4 | 4–5 |
| `bm25+onnx-rerank-20` | `dev` | 17–13 (p 0.59) | 4–3 | 4–3 |
| `onnx-dense` | `holdout` | 12–17 (p 0.46) | 4–0 (p 0.13) | 3–5 |
| `onnx-hybrid` | `holdout` | 11–8 (p 0.65) | 5–2 | 3–0 (p 0.25) |
| `bm25+onnx-rerank-20` | `holdout` | 12–4 (p 0.077) | 5–3 | 2–0 |

**By ADR-0009's rule, no Candidate Arm qualifies, so `bm25` stays the Shipped Arm.** On
`dev`, no Arm is distinguishably better on Fact Recall, which is the first condition.
`bm25+onnx-rerank-20` would fail the latency condition anyway: its warm band is `~1s`
against the rule's `~100ms`. The two ONNX embedding Arms are inside it (`~10ms` warm). The
rule reads the warm band only, so their `~1s` load band doesn't count against them. `holdout`
confirms the result.

This is **indistinguishable, not a BM25 win**. Fact Recall is compared per Required
Fact, so `dev`'s 152 facts give the test the most data of the three metrics. Still, each
Arm disagreed with `bm25` on only 30 to 43 of them, and the splits were close to even. The
largest gap, re-ranking's 12–4 on `holdout`, is the kind of difference more paraphrase,
conceptual and visitor-origin cases could confirm or dissolve (ADR-0009's Consequences).
Each Arm's answers were generated afresh, so some of these disagreements are model noise,
not retrieval.

The run billed `gpt-6-luna` 334k tokens for answers and 330k for claim splitting, and Jev
8.2M input tokens.

## Not yet measured

Retrieval quality is only half of a RAG system's behaviour, and generation is now gated
and published too, for the Shipped Arm and, by the manual comparison run, for every
Candidate Arm. Still open: adversarial/prompt-injection robustness, and multi-turn
conversations.
