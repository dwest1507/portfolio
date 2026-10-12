---
status: accepted
---

# The Shipped Arm is chosen from Candidate Arms by answer quality, defaulting to keyword search

ADR-0004 established that the Shipped Arm is whichever Arm the harness picks. This records
how it picks.

**Only Candidate Arms are eligible**: Arms that could run in production without bringing a
GPU-oriented ML runtime back into the image ADR-0004 shrank from 17.2GB to 544MB, such as
ONNX-runtime models or a hosted embedding API. The existing torch-based Arms remain as
Reference Arms and no new ones are added; a Scoreboard of Arms nobody can ship is a list
of upper bounds nobody can act on.

**The rule**, applied to a comparison run on `dev` and confirmed on `holdout`:

1. Keyword search (BM25) remains the Shipped Arm by default: no model, no network call,
   lowest Latency Band.
2. A Candidate Arm replaces it only if it is distinguishably better on Fact Recall
   (ADR-0006's test), not distinguishably worse on Faithfulness or Decline accuracy, and
   its Latency Band is no worse than `~100ms` warm.
3. Retrieval metrics explain a result but do not decide it: a hit@5 gain that does not
   change answers does not justify a model in the serving path.
4. Among qualifying Arms, the cheapest to run wins: no model, then local ONNX, then a
   hosted API.

Fact Recall decides here, although it is ungated in ADR-0007, because Arms differ only in
what they retrieve, and Fact Recall is the generation metric that reflects retrieval.

## Consequences

- Until the Golden Set holds many more paraphrase, conceptual and visitor-origin cases,
  this rule is conservative: an Arm genuinely better on those questions may not register
  as distinguishable overall, and the Verdict Line says so rather than declaring BM25 the
  winner.
- Changing a measured Arm's definition (such as its re-ranking candidate pool) creates a
  new Arm rather than editing the old one, so historical measurements keep their meaning.
