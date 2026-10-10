---
status: accepted
---

# Generated answers are evaluated by a separate harness, judged by a pinned external model

Retrieval metrics say whether a relevant chunk reached the model, not whether the answer
was right, stayed inside its context, or declined when it should have. A second harness
measures generated answers against the same Golden Set and Splits.

It is separate from the retrieval harness rather than a flag on it. The retrieval harness
is deterministic, offline and free, which is what makes its Floor trustworthy and its
publish step idempotent; the generation harness is none of those. ADR-0005's "zero dynamic
LLM calls" therefore stays true of the retrieval harness and does not apply to this one.

## Decisions

- **Judge: TypeSafe's Jev, pinned to an exact version** (`jev-1.13.0`, never `jev-latest`).
  It returns typed judgments with probabilities, its quota is independent of the generation
  provider, and it is from a different model family than the generator, which avoids
  self-preference bias. It is a paid service (fractions of a cent per run), accepted as an
  exception to the free-tier preference.
- **Claims are sentences, split by code.** Jev is weak on multi-claim input, long context
  and negation, so each factual sentence is judged against one retrieved chunk at a time;
  a separate yes/no question filters out filler sentences, and Declines are detected
  separately rather than judged for support.
- **Metrics:** Fact Recall (Required Facts conveyed, judged on meaning), Faithfulness,
  Contradictions (listed individually), and Decline accuracy in both directions.
- **Gated:** Faithfulness and Decline accuracy, on the Shipped Arm, in the PR gate, with a
  path filter narrowed to generation-relevant files. Floors are set from the spread of
  three identical runs, not guessed.
- **Not gated:** Fact Recall (it mostly re-measures retrieval, which has its own Floor) and
  Contradictions (a zero-tolerance Floor on a judged quantity would fail on judge error).
- **Production generates at temperature 0**, as the harness does, so the Floor defends
  what is actually served.
- **Arm comparisons run on demand, not per PR.** A manually triggered comparison run
  measures every Candidate Arm; Reference Arms are never run through generation.

## Considered Options

- **A Groq model as Judge** — rejected: it shares the production quota and the
  generator's provider.
- **An LLM rewriting answers into atomic claims** — rejected for now: a second unchecked
  LLM step. Revisit if the hand-labelled validation set shows Jev's disagreements cluster on
  compound sentences.
- **Exact-string `must_include` checks** — rejected: they fail on wording, not on wrong
  answers.

## Consequences

- Results publish to a separate `generationResults.json` with its own `MEASURED_KEYS`, in
  two sections with their own provenance: the Shipped Arm (latest `main` run) and the
  comparison (latest manual run). Metrics are rounded to a step size derived from observed
  run-to-run spread, so noise alone never produces a results commit.
- The generation model ID and Judge version are part of the measurement; a change to
  either is a new measurement, as a Corpus change is.
- Before any Jev judgment gates a build, it is validated against roughly 30 hand-labelled
  sentences from this domain.
