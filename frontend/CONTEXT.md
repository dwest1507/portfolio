# Frontend

The portfolio site. Its project pages include the public write-up of the retrieval
evaluation, which publishes measured results rather than describing them.

## Language

### Publishing evaluation results

**Findings Log**:
The append-only, hand-written record of what an evaluation showed and what changed in the
code because of it. Entries are added, never rewritten. It is the evidence that
measurement drives decisions, and it is the one part of the write-up a human authors.
_Avoid_: Changelog, results log, history, post-mortems

**Finding**:
One entry in the Findings Log: a dated judgement naming what was concluded and what
changed, alongside the metric that moved. A Finding is a human conclusion and cannot be
derived from metrics alone.
_Avoid_: Result, insight, learning

**Scoreboard**:
The rendered comparison of every Arm in the most recent Measured Run. Its contents are
generated, so it carries no hand-written claim about which Arm wins.
_Avoid_: Results table, metrics table, leaderboard

**Verdict Line**:
The single generated sentence naming the Shipped Arm and the Arm that currently leads on
the gating metric. It is derived from the Measured Run so it can never contradict the
Scoreboard.
_Avoid_: Summary, conclusion, takeaway
