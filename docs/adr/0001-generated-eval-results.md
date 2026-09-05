---
status: accepted
---

# Published evaluation results are generated, never hand-written

The public write-up at `/projects/portfolio` and `docs/evaluation.md` both publish
retrieval metrics. Rather than transcribing numbers into prose, the `Retrieval eval` CI
job writes a Measured Run to `frontend/data/evalResults.json` and commits it on pushes to
`main`; both surfaces render from that one file. The evaluation harness owns each Arm's
label, its recruiter-facing description, its engineer-facing note, and which Arm is the
Shipped Arm, so adding or removing an Arm requires no frontend change.

No sentence anywhere may hand-assert which Arm wins. Claims of that kind are emitted as a
generated Verdict Line, which names the Shipped Arm and the Arm currently leading on the
gating metric. This is what makes the write-up durable: when the retrieval architecture
changes, the page's conclusions change with it and cannot fall out of step with its own
table.

## Considered Options

- **Serving results from a backend endpoint** — rejected. The data originates in the
  repository, so fetching it over the network only adds a cold-start failure mode and a
  reason for the page to render an empty table.
- **Fetching the CI artifact during the Vercel build** — rejected. It puts a credential
  and a network call inside a build whose failure handling we do not control.

## Consequences

- The eval job needs `contents: write`. Its commit touches only `frontend/data/**` and
  `docs/evaluation.md`, neither of which matches `backend-ci.yml`'s path filters, so the
  commit cannot retrigger the job.
- Results are committed only from `main`. Pull-request runs measure and gate but never
  write, so branch results cannot race into the published file.
- Metrics are **not** rendered as a time series. Corpus changes move every metric, so
  values from different Corpora are not comparable and a trend line would report corpus
  growth as a quality decline. The Findings Log carries the history instead, because each
  entry states its own corpus context.
