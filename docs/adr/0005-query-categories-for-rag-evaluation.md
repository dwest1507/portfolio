---
status: accepted
---

# Query Categories partition the Golden Set by lexical and conceptual relationship to the Corpus (Schema v3)

The portfolio chatbot's retrieval evaluation was previously evaluated against 55 founding
questions written as direct paraphrases of recruiter Q&A in `docs/chatbot-questions.md`. As
recorded in ADR-0004, this condition heavily flattered lexical overlap (BM25) over semantic
(dense and hybrid) retrieval because queries drew upon the same vocabulary as the answer
chunks, and relevance was judged by phrase presence.

When visitors ask questions using different vocabulary, colloquialisms, or conceptual
synthesis across projects, keyword retrieval returns empty contexts. Evaluating only
in-vocabulary queries risked overstating production retrieval capabilities and hid the
distinction between where BM25 is sufficient and where semantic search is necessary.

To remedy evaluation bias without compromising historical continuity, the Golden Set is
partitioned into three canonical **Query Categories**, and published evaluation documents
advance to **Schema Version 3**.

## Taxonomy

Every case in the Golden Set belongs to exactly one of three Query Categories:

- **`direct`**: In-vocabulary questions using wording found directly in the Corpus. The 55
  founding cases all carry this label, preserving historical benchmarks.
- **`paraphrase`**: Out-of-vocabulary factual questions targeting specific answers while
  deliberately avoiding Corpus keywords.
- **`conceptual`**: Multi-angle, thematic, or cross-project synthesis queries requiring
  semantic understanding rather than literal phrase matches.

## Offline Generation and Human Curation

Candidate questions for `paraphrase` and `conceptual` categories are drafted offline with
explicit negative-keyword constraints (verifying candidate queries do not duplicate Corpus
keywords) and curated into the Golden Set in reviewed batches.

The evaluation harness performs zero dynamic LLM calls during execution or in CI. Evaluation
remains deterministic, fast, offline, and repeatable.

## Split Invariance

Cases continue to be partitioned into `dev` and `holdout` splits via the deterministic hash
rule:

$$\text{sha256}(\text{salt} + \text{":"} + \text{id}) < \text{holdoutBelow}$$

Because the split assignment function depends solely on the case's individual `id` and the
frozen salt, adding new cases in new Query Categories never reshuffles existing cases across
the `dev`/`holdout` boundary.

## Schema Version 3 Data Contract

Published evaluation documents (`frontend/data/evalResults.json`) advance from `schemaVersion: 2`
to `schemaVersion: 3`.

- Top-level metadata adds `categories: string[]`, enumerating the categories evaluated in the run.
- Each entry in `arms` retains aggregate `metrics` and gains a `byCategory` mapping:
  `Record<string, Record<string, number>>`, recording per-category summary metrics (e.g.
  `recall@k`, `hit@k`, `mrr`, `ndcg@k`).
- Re-measurement detection (`MEASURED_KEYS`) includes `categories`, ensuring category changes
  trigger updates even if aggregate metrics happen to align.
- The public Scoreboard component consumes Schema Version 3 contracts cleanly without
  regressions on aggregate presentation.

## Floor Gating

Regression Floors (`hit@5 >= 0.85`, `mrr >= 0.75`) remain enforced on the Shipped Arm across
the **full** Golden Set (`--split all`).

Category-level metrics are diagnostic: they are displayed in the harness CLI and published in
the data contract, but are not independently gated by floors. Gating individual categories
prior to completing dataset expansion would introduce arbitrary constants before baseline
empirical measurement.

## Amendment (2026-10-09)

- **Hard cases are written to be realistic, not adversarial.** The negative-keyword
  constraint above produced questions no visitor would type ("What level of national
  defense vetting has been granted to him?"). New `paraphrase` and `conceptual` cases are
  phrased as a recruiter or engineer would actually ask, avoid the Corpus's wording because
  people do rather than by rule, and each targets a different chunk where possible, since
  ten questions about one chunk are one sample.
- **Growth targets the categories where Arms disagree.** `direct` cases are added only to
  cover new Corpus content; `paraphrase` and `conceptual` grow toward ~50 each, because only
  questions Arms disagree on can distinguish them (ADR-0006).
- **The Golden Set gains Out-of-Scope Cases**, scored by the generation harness only.
- **"Zero dynamic LLM calls" is a property of the retrieval harness.** The generation
  harness (ADR-0007) is separate and makes such calls by design.
