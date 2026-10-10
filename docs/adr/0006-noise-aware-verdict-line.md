---
status: accepted
---

# The Verdict Line names a leader only when the difference is not sampling noise

The Verdict Line used to name whichever Arm had the highest gating metric, even when the
gap was a single question out of 33. That is how the public page came to say keyword
search "leads" on a Corpus where it no longer did, and how findings were drawn from
differences of 0.03.

The Verdict Line now compares every Arm against the Shipped Arm using only the questions
the two disagree on (an exact sign test on the discordant pairs, McNemar's test, at
p < 0.05). An Arm is called ahead or behind only when that split is too lopsided to be
chance; otherwise the line says the two are indistinguishable on this sample. The
Scoreboard gains a per-Arm column of questions won and lost against the Shipped Arm, so a
reader can see the raw disagreement without reading any statistics.

This extends ADR-0001's rule — no hand-written claim about which Arm wins — from claims a
person makes to claims the noise makes.

## Consequences

- The published document moves to `schemaVersion: 4`, because the test needs per-question
  outcomes, not only averages.
- On the held-out sample the honest Verdict Line will usually read "no Arm is
  distinguishable from the Shipped Arm". That is the intended outcome, not a defect.
  Distinguishing Arms requires a Golden Set grown in the categories where Arms disagree;
  see ADR-0005's amendment.
- Bootstrap intervals for rank metrics (MRR) appear in `docs/evaluation.md` only; they are
  not published on the page.
