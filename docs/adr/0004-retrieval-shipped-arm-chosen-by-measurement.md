---
status: accepted
---

# The shipped retrieval Arm is whichever one the harness picks, and only it is gated

The pipeline was built as hybrid retrieval — weighted reciprocal-rank fusion of FAISS
semantic search and BM25 — followed by cross-encoder re-ranking. The evaluation harness
measured that configuration against plain BM25 on this Corpus and it lost on every metric.
A `bm25+rerank` Arm, added to ask the structural question rather than the tuning one,
showed the dense stage contributed nothing the re-ranker could not recover; the
cross-encoder then failed the same test against BM25 alone.

Production therefore serves BM25 only. Three decisions follow from that, and they are the
ones worth recording.

## The dense and re-ranking stages are retired from production, not from the codebase

`RAGPipeline` still implements `dense_search`, `hybrid_search` and `rerank`, and
`run_eval.py` still measures all of them on every run. This Corpus embeds its own expected
questions — `docs/chatbot-questions.md` is written as recruiter Q&A and the Golden Set asks
paraphrases of it — which is exactly the condition that flatters lexical retrieval. The
result is expected to reverse as the Corpus grows toward content that does not anticipate
the query phrasing, and when it does the harness should be what says so.

Deleting the implementations would make that a rebuild from scratch rather than a measured
decision, and would silently discard the comparison the public page exists to publish.

What the retirement does remove is cost: `faiss-cpu` and `sentence-transformers` moved to
the `dev` dependency group, so the production image installs neither and bakes in no model
weights. 87 locked packages became 40, and the built image went from 17.2GB to 544MB —
mostly not the weights but `torch`'s default Linux wheels, which carry the NVIDIA CUDA
runtime into a container with no GPU, duplicated again by the `chown -R` layer.

`app/rag/pipeline.py` imports both libraries inside its lazy loaders rather than at module
scope, which is what lets the same module serve a container that has neither installed and
still implement the Arms that need them. That is a load-bearing detail with no local
symptom, so `test_the_pipeline_module_imports_without_the_eval_only_libraries` imports
`app.main` in a subprocess with both libraries blocked: a module-level `import faiss` would
pass every other test and fail only on deploy.

### Rejected: keep the Arms but behind a feature flag

A runtime switch would have kept the ML libraries in the production image to serve a code
path nothing selects, which is the cost this decision exists to remove. The harness is
already the mechanism for running a non-shipped Arm.

## Only the Shipped Arm has a Floor

`THRESHOLDS` is keyed off `shipped_arm_id()` rather than naming Arms, so the gate follows
production automatically.

A Floor exists to stop a change degrading what a visitor is served, and nothing is served
by an Arm production does not run. Floors are also calibrated against a Corpus: with four
gated Arms, every Corpus change means four constants to re-justify, and a constant nudged
to make a build pass is precisely the magic number this harness argues against. `hybrid`
in fact fell below the old MRR Floor on the rebuilt Corpus — a number nobody is served by,
which under the old scheme would have been fixed by editing the Floor.

Ungated Arms are still measured, published and compared. `--check` names every ungated Arm
explicitly and a run that gates nothing is a failure, so this cannot decay into a gate over
nothing.

## The Golden Set is split, and only the held-out portion is published

An Arm chosen by a measurement must not be scored by the questions that chose it. The
Golden Set carries a frozen `dev` / `holdout` Split; decisions are made against `dev`, and
`--publish` refuses any Split but `holdout`.

`--check` still gates the whole set. The Floors are regression detection rather than a
target anything is tuned toward, so there is no leakage to protect against and the larger
sample makes them less twitchy. The two invocations in `scripts/backend-eval.sh` measure
different samples deliberately.

Assignment is deterministic — a case is held out when `sha256(salt + ":" + id)` sorts below
the `holdoutBelow` boundary recorded in `golden_set.json` — and the labels are recorded
rather than recomputed per run. The rule reads one id at a time, which is what lets both be
true at once: a test can recompute it to catch a question hand-edited across the line,
without that test ever demanding the frozen labels change. A rank-based cutoff ("the first
40%") could not do both, because its boundary moves with the size of the set.

## Consequences

- The published sample is 22 questions. hit@5 moves in steps of ~0.045, so published
  numbers are coarser than a run over all 55. That is the price of them measuring rather
  than scoring the winner of their own selection.
- BM25-only retrieval returns *nothing* when a query shares no term with any chunk, where
  hybrid always returned its top five. Preferred: an empty context leaves the system
  prompt's "say so honestly" instruction unopposed.
- `SCHEMA_VERSION` is 2. A v1 published document measured the whole Golden Set and is not
  comparable with a v2 held-out run.
- Adding a question changes the `dev`/`holdout` balance but not any existing assignment,
  because the recorded Split is frozen per case.
