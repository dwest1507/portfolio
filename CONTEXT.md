# Portfolio

Personal portfolio site with a retrieval-augmented question answering pipeline and evaluation harness.

## Frontend

The portfolio site. Its project pages include the public write-up of the retrieval evaluation, which publishes measured results rather than describing them.

### Language: Publishing evaluation results

**Findings Log**:
The append-only, hand-written record of what an evaluation showed and what changed in the code because of it. Entries are added, never rewritten. It is the evidence that measurement drives decisions, and it is the one part of the write-up a human authors.
_Avoid_: Changelog, results log, history, post-mortems

**Finding**:
One entry in the Findings Log: a dated judgement naming what was concluded and what changed, alongside the metric that moved. A Finding is a human conclusion and cannot be derived from metrics alone.
_Avoid_: Result, insight, learning

**Scoreboard**:
The rendered comparison of every Arm in the most recent Measured Run. Its contents are generated, so it carries no hand-written claim about which Arm wins.
_Avoid_: Results table, metrics table, leaderboard

**Verdict Line**:
The single generated sentence comparing the Shipped Arm against every other Arm on the gating metric. It names an Arm as ahead or behind only when the questions the two Arms disagree on are too lopsided to be sampling noise; otherwise it says they are indistinguishable. It is derived from the Measured Run so it can never contradict the Scoreboard.
_Avoid_: Summary, conclusion, takeaway

## Backend

The retrieval-augmented pipeline that answers questions about David's experience, and the harnesses that measure whether its retrieval and its answers actually work.

### Language: Retrieval evaluation

**Arm**:
One retrieval configuration measured by the harness, such as keyword-only or hybrid fusion followed by re-ranking. Arms are defined in the harness, which owns both their identity and how they are described to a reader.
_Avoid_: Variant, strategy, mode, config

**Shipped Arm**:
The single Arm that mirrors what the production pipeline actually runs. Exactly one Arm carries this designation at a time, and it is the only Arm a Floor gates. An Arm losing the designation is not retired from the harness: the code that implements it and the measurement of it both remain, so the decision can be revisited on evidence.
_Avoid_: Default arm, live arm, current config

**Candidate Arm**:
An Arm that could become the Shipped Arm within production's constraints — notably, without bringing a GPU-oriented ML runtime into the served image. Only Candidate Arms are eligible when the Shipped Arm is chosen.
_Avoid_: Contender, option

**Reference Arm**:
An Arm kept in the harness as a baseline for comparison but not eligible to ship. Its scores show what is possible, not what is on offer. No new Reference Arms are added.
_Avoid_: Upper bound, oracle, legacy arm

**Golden Set**:
The hand-labelled questions both retrieval and generated answers are scored against. An answerable case carries the Relevant Phrases that ground it and the Required Facts a correct answer conveys; an Out-of-Scope Case carries neither.
_Avoid_: Test set, eval set, question bank

**Out-of-Scope Case**:
A Golden Set case the Corpus cannot answer. Retrieval is not scored on it; the answer is scored on whether it Declines. It shares the Golden Set's Splits rather than forming a set of its own.
_Avoid_: Negative case, unanswerable question, adversarial case

**Split**:
One of the two portions the Golden Set is divided into. Decisions are made against the development portion; the held-out portion is measured but never consulted while making one, and is what a published Measured Run reports. A Split is a property of a case, frozen in the Golden Set rather than computed per run, and decided by that case's id alone — so growing the Golden Set never moves a case that already has one. A held-out case's Relevant Phrases may be repaired, but only for reasons independent of any Arm's results, and never with those results in view.
_Avoid_: Fold, sample, train/test, validation set

**Relevant Phrase**:
A string whose presence in a chunk, beginning at the start of a word, makes that chunk relevant to a given question. Relevance is labelled by phrase rather than by chunk identity so that labels survive re-chunking. A phrase so common that it marks a large share of the Corpus relevant is a labelling defect, not a label.
_Avoid_: Ground truth, gold label, answer key

**Measured Run**:
One execution of the harness over the Golden Set, carrying its metrics, the corpus it was measured against, and the commit it was measured at. A metric is only meaningful alongside the run that produced it.
_Avoid_: Result, snapshot, benchmark

**Latency Band**:
The order-of-magnitude cost of answering a query with an Arm, published in place of a raw timing because raw timings vary between runs and machines. Only a change of band is a change in what was measured.
_Avoid_: Latency, speed, response time, performance

**Floor**:
A minimum metric value below which a Measured Run fails the build. A Floor sits beneath measured performance to catch regressions, and is never a target to optimise toward. Only the Shipped Arm has one — a Floor defends what a visitor is served, and nothing is served by an Arm production does not run.
_Avoid_: Threshold, target, baseline, SLA

**Corpus**:
The chunked text the pipeline retrieves over, assembled from the resume, the question document, and the project write-ups. Metrics from different Corpora are not comparable.
_Avoid_: Index, knowledge base, dataset

**Chunk**:
One retrievable unit of the Corpus, cut along the structure of its source: a single question-and-answer pair, a single project section, or a single resume entry. It carries the heading that says what it is about, so it reads as self-contained without its neighbours.
_Avoid_: Passage, document, segment, snippet

**Query Category**:
The semantic classification of a case in the Golden Set (`direct`, `paraphrase`, or `conceptual`), describing how closely its question matches the phrasing of the Corpus. Used to diagnose how well an Arm generalizes beyond literal in-vocabulary queries without conflating distinct failure modes.
_Avoid_: Query type, bucket, tag, difficulty tier

**Case Origin**:
Whether a Golden Set case was authored by hand or derived from a question a real visitor asked. Independent of Query Category: a visitor's question can be direct, paraphrase, or conceptual.
_Avoid_: Source, provenance, real vs synthetic

**Empty Context**:
The outcome where retrieval returns no chunks for a question, so the model is shown nothing to answer from. Expected and preferred over irrelevant context, but its rate in production is measured rather than assumed.
_Avoid_: No results, miss, null retrieval

### Language: Generation evaluation

**Judge**:
The model that decides whether a generated answer is supported by, contradicted by, or silent about the retrieved chunks. It is pinned to an exact version, because a Judge that changes silently makes Measured Runs incomparable just as a changed Corpus does.
_Avoid_: Grader, evaluator, critic

**Required Fact**:
A statement, written as a full sentence, that a correct answer to a Golden Set case must convey. Judged on meaning rather than wording.
_Avoid_: Expected answer, must-include string, key fact

**Faithfulness**:
The share of an answer's factual sentences that at least one retrieved chunk supports. It measures whether the answer stays inside its context, not whether it is correct.
_Avoid_: Groundedness, accuracy, hallucination rate

**Contradiction**:
A sentence in an answer that a retrieved chunk states the opposite of. Reported individually for review rather than averaged, because each one is a false statement about David.
_Avoid_: Hallucination, error

**Decline**:
An answer that says the information is not available rather than answering. Correct for an out-of-scope question; a failure for an answerable one.
_Avoid_: Refusal, abstention, fallback
