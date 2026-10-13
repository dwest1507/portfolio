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

## Amendment (2026-10-12)

- **Results are pushed by a GitHub App, not the job token.** `main`'s ruleset requires a
  pull request, and the job's `GITHUB_TOKEN` cannot be a ruleset bypass actor, so every
  publish push was rejected (`GH013`) once the lockfile no longer broke the step first. The
  `dwest1507-eval-publisher` App (Contents read and write, installed on this repository
  only) is on the ruleset's bypass list. The publishing jobs check out without persisted
  credentials and keep the read-only job token; `.github/actions/publish-results` mints an
  hour-long App token only after the measurement, so no eval code runs holding a token
  that can write. This replaces the `contents: write` consequence above.
- **Deletion and force-push protection sit in a separate ruleset with no bypass.** A bypass
  covers every rule in its ruleset, so the App is on `main`'s pull-request ruleset only, and
  `main-history` blocks deleting and force-pushing `main` for everyone, the App and admins
  included.
- **A publish commit now triggers workflows.** Pushes made with `GITHUB_TOKEN` trigger
  nothing; the App's do. Frontend CI checks the published files, and the path filters
  still keep the eval jobs (and their paid calls) from retriggering.
- **Considered:** a personal access token (expires, bypasses every rule, and credits the
  owner with generated commits) and results pull requests (each publish would wait for an
  approval).

## Amendment (2026-10-13)

- **The retrieval eval runs from its own workflow and skips unchanged inputs** (#97). It
  moved from `backend-ci.yml` to `retrieval-eval.yml`, whose path filter covers only what
  can move a retrieval measurement. Its publish commit still touches only
  `frontend/data/**` and `docs/evaluation.md`, outside that filter, so it still cannot
  retrigger the job.
- **The published run records an input fingerprint**, `inputsFingerprint`: a hash of the
  Corpus and index files, retrieval code, harness, Golden Set, retrieval Floors record and
  `backend/uv.lock` with the `backend` package's own version stripped
  (`backend/eval/inputs.py`). A run whose inputs match it skips the measurement, gate and
  publish both, and logs why. The release merge #95 cost 4m53s of measuring and published a
  false result (#96); a version bump cannot move a metric.
- **A changed fingerprint is published even when no number moved.** Otherwise the record
  keeps a stale fingerprint, and every later run measures again until a number happens to
  move. This adds a publish commit after an input change that measured the same numbers, an
  exception to "the commit history records the runs where a number moved".
- **Only a CI run records a fingerprint.** Skipping is safe only because the fingerprint
  comes from a run that passed the gate, and on `main` CI publishes only after `--check`
  passes in the same job. A local `--publish` gates nothing, so it records none, and a run
  without a fingerprint never replaces one for that reason alone.
- **Considered:** a path filter alone, which cannot tell a release-please version bump in
  `uv.lock` from a dependency bump in the same file; and a skip condition in the workflow on
  the commit author or message, which would also skip a release that carried a real change.
