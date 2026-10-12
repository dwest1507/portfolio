---
status: accepted
---

# Floors follow the instrument, never the system: Recalibration

On the PR that delivered spec #62, both gates failed: retrieval MRR 0.705 < 0.750, and
Decline accuracy 0.901 < 0.915. On the original 107 cases both still cleared their Floors;
the 24 new cases caused both failures. The Floors had been derived on a Golden Set that no
longer existed, nothing said when a Floor must be re-derived, and the retrieval Floors had
never been derived by any rule at all. A gate that cannot tell a regression from a change
of instrument invites the one fix this project argues against: editing a number until the
build passes.

A **Recalibration** (`CONTEXT.md`) is the answer: re-deriving a Floor by its fixed rule
because what it measures with changed.

## Decisions

- **Triggers: the Golden Set or the instrument, never the system.** A Recalibration is
  required when the Golden Set changes (cases added or removed; a question, Relevant
  Phrase, Required Fact or `answerable` edited) or the instrument does (Judge version,
  Judge question wording, splitter model, generation model, reasoning effort, metric
  definitions). Corpus, prompt, chunking and retrieval-code changes are never triggers:
  they are what the gates exist to judge, and a Floor that followed them could never catch
  one.
- **The same-change rule.** A Recalibration happens in the change that caused it, so any
  drop is visible there, beside its cause, rather than surfacing later as a red gate on
  someone else's PR.
- **The fixed-rule-only rule.** Every Floor is derived by its gate's fixed rule from a
  Measured Run and never chosen by hand. Floors live in one committed **Floors record** per
  gate (`backend/eval/floors/<gate>.json`), which replaces the Floor constants in code.
  Each record holds the Floor per metric, the rule, its inputs, a fingerprint and the
  commit the inputs were measured at, so anyone can redo the arithmetic. Only the
  recalibrate command (`backend/eval/recalibrate.py <gate>`) writes a record, and a test
  fails if a record's Floors no longer follow from the inputs beside them.
- **Retrieval rule.** Floor = measured − 2/n, rounded down to 0.005, where n is the
  answerable cases on the full Golden Set, for the Shipped Arm only (ADR-0004). Two
  cases' worth states the tolerated regression in questions. Retrieval is deterministic,
  so the margin is a tolerance for a small real loss, not headroom for noise. On the
  Golden Set of 2026-10-11 (n = 111): hit@5 0.865 → 0.845, MRR 0.705 → 0.685.
- **Generation rule.** The variance rule of ADR-0007, applied to five judged runs of the
  Shipped Arm: the lowest run minus twice the range, at least one rounding step, rounded
  down to the metric's step. The rounding steps are re-derived from the same runs'
  held-out range. Three runs understated the noise, so the study grows to five; the
  Measured Runs already paid for are re-judged rather than regenerated.
- **A fingerprint per gate.** Each is a stable hash over canonicalized case fields, sorted
  by case id, covering exactly what can move that gate's metrics:
  - retrieval: question, Relevant Phrases, `answerable`;
  - generation: question, Required Facts, `answerable`, plus the Judge version, the Judge
    questions, the splitter model, the generation model and the reasoning effort.

  Separate fingerprints mean a free retrieval label repair never forces a paid generation
  study, and a Required Fact edit never stales the retrieval Floors.
- **Stale fails first, and on its own.** A gate whose record's fingerprint no longer
  matches fails with "Floors stale: Recalibrate" before comparing any metric, and says
  nothing about the metrics, so a stale record is never mistaken for a regression or
  hidden behind one. A test in the ordinary suite runs the same comparison against the
  committed Golden Set, so staleness fails on the PR for free, before any eval job (paid
  or not) starts.

## Considered Options

- **Recalibrating on every change, Corpus included** — rejected: a Floor that moves with
  the system can never catch a regression of it.
- **Choosing Floors by judgment, with the reasoning written down** — rejected: it is the
  failure mode this ADR exists to close. A written reason does not stop the next number
  being nudged to pass.
- **A paired comparison against `main`'s latest Measured Run, or bootstrap-derived
  Floors** — deferred (spec #62, Out of Scope). Both may be better gates; neither is
  needed to make the absolute Floors honest.
- **One fingerprint over the whole Golden Set file** — rejected: a split label, category
  or Required Fact edit would stale the retrieval Floors for nothing, and every retrieval
  label repair would force a paid generation study.

## Consequences

- A Golden Set edit now carries its Recalibration in the same change. For retrieval this
  is free and deterministic: run the command and commit the record. For generation it
  means a paid five-run study, which is why the fingerprints are kept per gate.
- A drop caused by a new instrument is visible in the record's diff, beside the Golden Set
  diff that caused it, instead of in a failing gate.
- Until a gate's record is recalibrated after a trigger, that gate reports stale. That is
  correct: gating against Floors from a Golden Set that no longer exists is worse. The
  first generation record was carried over from the three-run study's constants with no
  fingerprint, so it is stale until the five-run study recalibrates it (#91); until then
  the ordinary suite's check of it is a strict expected failure, which that
  Recalibration must remove.
- ADR-0004's and ADR-0007's descriptions of how Floors are set are superseded by this ADR,
  and each carries a pointer to it.
