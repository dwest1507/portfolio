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
The single generated sentence naming the Shipped Arm and the Arm that currently leads on the gating metric. It is derived from the Measured Run so it can never contradict the Scoreboard.
_Avoid_: Summary, conclusion, takeaway

## Backend

The retrieval-augmented pipeline that answers questions about David's experience, and the harness that measures whether its retrieval actually works.

### Language: Retrieval evaluation

**Arm**:
One retrieval configuration measured by the harness, such as keyword-only or hybrid fusion followed by re-ranking. Arms are defined in the harness, which owns both their identity and how they are described to a reader.
_Avoid_: Variant, strategy, mode, config

**Shipped Arm**:
The single Arm that mirrors what the production pipeline actually runs. Exactly one Arm carries this designation at a time, and it is the only Arm a Floor gates. An Arm losing the designation is not retired from the harness: the code that implements it and the measurement of it both remain, so the decision can be revisited on evidence.
_Avoid_: Default arm, live arm, current config

**Golden Set**:
The hand-labelled questions retrieval is scored against, together with the phrases an answer must be grounded in.
_Avoid_: Test set, eval set, question bank

**Split**:
One of the two portions the Golden Set is divided into. Decisions are made against the development portion; the held-out portion is measured but never consulted while making one, and is what a published Measured Run reports. A Split is a property of a case, frozen in the Golden Set rather than computed per run, and decided by that case's id alone — so growing the Golden Set never moves a case that already has one.
_Avoid_: Fold, sample, train/test, validation set

**Relevant Phrase**:
A string whose presence in a chunk makes that chunk relevant to a given question. Relevance is labelled by phrase rather than by chunk identity so that labels survive re-chunking.
_Avoid_: Ground truth, gold label, answer key

**Measured Run**:
One execution of the harness over the Golden Set, carrying its metrics, the corpus it was measured against, and the commit it was measured at. A metric is only meaningful alongside the run that produced it.
_Avoid_: Result, snapshot, benchmark

**Floor**:
A minimum metric value below which a Measured Run fails the build. A Floor sits beneath measured performance to catch regressions, and is never a target to optimise toward. Only the Shipped Arm has one — a Floor defends what a visitor is served, and nothing is served by an Arm production does not run.
_Avoid_: Threshold, target, baseline, SLA

**Corpus**:
The chunked text the pipeline retrieves over, assembled from the resume, the question document, and the project write-ups. Metrics from different Corpora are not comparable.
_Avoid_: Index, knowledge base, dataset
