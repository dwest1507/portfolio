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
- **Claims are sentences, split by code** (amended 2026-10-11: each sentence is then
  split into claims by an LLM, below). Jev is weak on multi-claim input, long context
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
  compound sentences. *Adopted 2026-10-11: they did; see the amendment below.*
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
  sentences from this domain. _(2026-10-11: this covers the Decline judgment too, against
  roughly 30 hand-labelled answers; see docs/evaluation.md, "Validating the Decline
  judgment".)_

## Amendment (2026-10-10)

- **OpenAI's candidates cannot generate at temperature 0.** `gpt-6-luna` and `gpt-6.1-sol`
  are reasoning models and reject any temperature but the default (1). Once generation
  moves to OpenAI, answers vary from run to run however the request is set, so "the same
  inputs give the same answer" no longer holds. What the eval and production share instead
  is the model, the prompt, `max_completion_tokens` and the **reasoning effort**, which is
  pinned (`low`, the one explicit value both candidates accept) and recorded with each run.
  Groq keeps generating at temperature 0 until the switch.
- **The variance study ran on Luna, not Groq.** The Floors defend what production serves,
  and production is moving to OpenAI (ADR-0008), so Floors measured on Groq at temperature
  0 would have understated the noise and been re-measured at the switch. If the selection
  rule picks Sol, the study is rerun on Sol.
- **Floors and the rounding step are derived by a fixed rule** (`eval/variance.py`; amended 2026-10-11 to one step per metric, below): the
  step is the smallest of 0.005 / 0.01 / 0.02 / 0.05 / 0.1 no smaller than any published
  metric's held-out range across three runs; each Floor is the lowest full-set run minus
  twice its range, at least one step, rounded down to the step. Three runs understate the
  noise, hence the factor of two. A change to the Judge's questions is a new measurement
  and the study is rerun, as it is for a new generation model.

## Amendment (2026-10-11): claims are split by an LLM

The condition for revisiting LLM claim splitting was met. Validating Jev against hand
labels (#70) found every Faithfulness disagreement on a compound sentence: a chunk
backing one part of a sentence made Jev call the whole sentence supported. Neither
cheaper fix worked (#81, docs/evaluation.md):

- **A strict `supports`** (every part), asked one chunk at a time, failed the sentences
  whose parts different chunks back. Jev also still passed most partly supported ones.
- **One question over the sentence and all its chunks** scored supported and unsupported
  sentences in overlapping ranges, so no threshold separated them.

So each factual sentence is now split into standalone claims, and each claim is judged
against each chunk. A sentence is supported only if every claim is, and different
chunks may support different claims. Sentences are still split by code first, and filler
is still dropped per sentence.

- **Splitter: OpenAI's `gpt-6-luna`**, reasoning effort `low`, given the question and the
  sentence, with structured output. Jev returns judgments, not text. Luna is already used
  by the harness, costs a few cents per judged run, and serves the OpenAI showcase
  (ADR-0008). Groq's free quota is shared with production until the switch, and
  `gpt-6.1-sol` costs about 20× as much.
- **The splitter is not validated alone.** The Judge validation's pass bar measures the
  splitter and Jev together, on held-out sentences. A splitter that drops or softens a
  detail shows up there as an unsupported sentence passed.
- **Self-preference risk is accepted.** Luna may also become the generator (ADR-0008), so
  it would split its own answers. It only rewrites sentences into claims, and Jev, from a
  different family, still judges every claim. The held-out bar would show a splitter that
  smooths claims into supportable ones.
- **Part of the measurement.** The splitter's reported model is recorded with every
  judged run, next to the Judge version. Its answers vary from run to run (no
  temperature), which adds to the run-to-run spread the Floors are set from.
- **Support threshold.** A chunk supports a claim when Jev finds `supports` more likely
  than not (P ≥ 0.5), not merely when `supports` is its likeliest answer. A sentence is
  dropped as filler only when Jev is confident it is filler (P(factual) < 0.2).
- **Cost.** Judging a full record now bills Jev ~1.95M input tokens, about three times
  as much as before, plus ~68k splitter tokens. That is still cents per run.

## Amendment (2026-10-11): a rounding step per metric

The fixed rule above set one rounding step from the largest held-out range among the
published metrics. Rerun with the fixed questions (#81), Fact Recall's held-out range
was 0.080, all of it from generation: Luna reworded 95 of 107 answers. One step for every
metric then became 0.1, and both Floors 0.80, which would fire only on a collapse.
Fact Recall is not gated, and its noise should not loosen the gated metrics.

Each published metric is now rounded to a step from its own held-out range, by the same
rule, and each Floor uses its own metric's step. David chose this over keeping the rule,
and over running more generations first. Measured values: Fact Recall 0.1, Faithfulness
0.05, Decline accuracy 0.005; Floors 0.85 and 0.915 (docs/evaluation.md).

## Amendment (2026-10-11): the gate generates with Luna before the switch

The gate (#71) generates with `gpt-6-luna` at reasoning effort `low`, while production
still serves Groq until ADR-0008's switch. The Floors were derived from Luna's
run-to-run spread, so gating a Groq run against them would compare against noise that was
never measured. And a full Golden Set run on Groq takes most of the free daily quota that
visitors share. Until the switch, the published Shipped Arm section therefore names Luna as
the generation model. If the selection picks a different model, the gate's model, its
price and the spread study change together.

Cost per answer is published to one significant figure. The spread study derived no
step for it, and billed tokens move with every reworded answer.
