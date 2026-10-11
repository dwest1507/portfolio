---
status: accepted
---

# Production generation moves from Groq to OpenAI, chosen by measurement

Generation ran on `openai/gpt-oss-120b` via Groq's free tier: 30 requests/min, 1k
requests/day, 8k tokens/min, 200k tokens/day, shared between visitors and CI. One
generation eval over the Golden Set uses roughly 60% of that day, and Groq's paid tier is
no longer offered. Separately, demonstrating the OpenAI API is a career goal for this
project.

Generation moves to the OpenAI API, but as a measured migration, not a configuration
swap: a Groq baseline is captured on both Splits while it is still available, the
candidates `gpt-6-luna` and `gpt-6.1-sol` are measured with the same harness and Judge,
and the choice is made on `dev` and confirmed on `holdout`.

## Selection rule

Prefer the cheapest model; pay only for a difference the data can see.

1. `gpt-6-luna` replaces Groq unless it is distinguishably worse (ADR-0006's test) on
   Faithfulness or Decline accuracy.
2. `gpt-6.1-sol`, at roughly 20× the price, replaces Luna only if it is distinguishably
   better on either.
3. Fact Recall breaks ties and never justifies an upgrade alone.

`gpt-6-astra` was excluded on cost without being measured.

## Consequences

- A paid model behind a public, anonymous endpoint makes abuse cost money. The per-IP rate
  limit is joined by a global daily request cap in the application, which degrades with a
  message, and a hard monthly budget on the OpenAI project, which is the backstop. CI and
  production use separate keys.
- Cost per answer is measured from billed `usage` and published alongside the Latency
  Band.
- Changing the model is changing what is served; any future model change goes through the
  same rule.

## Amendment (2026-10-11): how the rule is applied

ADR-0006's test pairs the two models' outcomes on the same questions. Applying it to
generation needed choices this ADR did not make (#72, `eval/select_model.py`):

- **Same contexts.** Candidates answer from the chunks stored in the Groq baseline
  (`run_generation.py --contexts`), not from retrieval over today's Corpus, so the model
  is the only variable. All three runs are judged by the same pinned Judge and splitter.
- **Faithfulness is paired per case.** It pools sentences, and two models' answers have
  different sentences. So a case counts as faithful when every factual sentence of its
  answer is supported. A case that either model declined, and every Out-of-Scope Case, has
  no Faithfulness outcome and is left out of the pairing. David chose this definition.
- **Decline accuracy is paired per case:** correct or not, over every case.
- **Fact Recall is paired per Required Fact,** since both models are asked the same facts.
- **A tie** is a candidate distinguishably better on one gated metric and worse on the
  other. Fact Recall breaks it: Sol replaces Luna only if it is also distinguishably ahead
  on Fact Recall.
- **The rule says nothing of Sol if Luna is rejected.** That case is left to David.
- **Cost per answer** is billed usage at OpenAI's list price, with every input token
  priced as uncached (an upper bound). The Groq baseline ran on the free tier and costs
  nothing.
- **One generation per model.** OpenAI's candidates vary from run to run (ADR-0007
  amendment), and one run of each is compared. Their run-to-run noise adds disagreements in
  both directions. That makes a real difference harder to call, while the test's false
  alarm rate stays at 5%.
