/**
 * The most recent measured run of the retrieval evaluation.
 *
 * `evalResults.json` is GENERATED. The `Retrieval eval` CI job runs the harness on pushes
 * to `main`, writes the file, and commits it — see docs/adr/0001-generated-eval-results.md.
 * Editing it by hand defeats the point: the next run overwrites it, and in the meantime the
 * site publishes a number nothing measured.
 *
 * Arm labels, descriptions and the `shipped` flag travel inside the document because the
 * harness owns them (`backend/eval/publish.py`). Nothing here knows which arms exist, so
 * adding or retiring one needs no change on this side.
 */
import run from './evalResults.json'

export interface EvalArm {
  /** Harness arm name, matching `--arms` in eval/run_eval.py. */
  id: string
  label: string
  /** Written for a non-specialist reader. */
  description: string
  /** The implementation detail `description` leaves out. */
  technical: string
  /** True for the one arm mirroring what production actually runs. */
  shipped: boolean
  /** Keyed by metric name, e.g. `hit@5`. Names come from `metricNames`. */
  metrics: Record<string, number>
}

export interface EvalRun {
  schemaVersion: number
  generatedAt: string
  /** Commit the run was measured on. */
  commit: string
  /** The CI job that produced the numbers, when a run produced them. */
  runUrl: string | null
  corpusChunks: number
  /** How many questions this run measured — the size of `split`, not of the whole set. */
  goldenQuestions: number
  /**
   * Which portion of the golden set was measured: `holdout` for a published run.
   * Configurations are chosen on the `dev` portion and reported on this one, so a number
   * on the page is never the number something was tuned against.
   */
  split: string
  topK: number
  /** The metric the verdict is decided on. */
  gatingMetric: string
  /** Metric column order, following the run's cutoff. */
  metricNames: string[]
  arms: EvalArm[]
}

export const evalRun: EvalRun = run as EvalRun

/** The arm scoring highest on a metric. Ties resolve to the earliest arm listed. */
export function leadingArm(metric: string, arms: EvalArm[] = evalRun.arms): EvalArm {
  return arms.reduce((best, arm) =>
    (arm.metrics[metric] ?? -Infinity) > (best.metrics[metric] ?? -Infinity) ? arm : best
  )
}

/** The arm mirroring production, if the run flagged one. */
export function shippedArm(arms: EvalArm[] = evalRun.arms): EvalArm | undefined {
  return arms.find((a) => a.shipped)
}

/**
 * One generated sentence placing the shipped configuration against the leading one.
 *
 * Derived rather than written so it cannot contradict the table beside it, and so it
 * changes on its own when the shipped configuration does. Mirrors `verdict_line()` in
 * backend/eval/publish.py.
 */
export function verdictLine(run: EvalRun = evalRun): string {
  const metric = run.gatingMetric
  const leader = leadingArm(metric, run.arms)
  const shipped = shippedArm(run.arms)
  const score = (arm: EvalArm) => (arm.metrics[metric] ?? 0).toFixed(3)

  if (!shipped) {
    return `${leader.label} leads on ${metric} (${score(leader)}). No arm is flagged as shipped.`
  }
  if (shipped.id === leader.id) {
    return `Production runs ${shipped.label}, which also leads on ${metric} (${score(shipped)}).`
  }
  return (
    `Production runs ${shipped.label}. On the current corpus, ${leader.label} ` +
    `leads on ${metric} (${score(leader)} vs ${score(shipped)}).`
  )
}

/** Display name for a metric column. `mrr` is an initialism; the rest read as written. */
export function metricLabel(metric: string): string {
  return metric === 'mrr' ? 'MRR' : metric
}

/**
 * How to describe the measured sample in one phrase.
 *
 * Derived from the run rather than written into the page, because which portion gets
 * published is the harness's decision (`PUBLISHED_SPLIT` in eval/run_eval.py). A page
 * that hardcoded "held-out" would keep saying it after that decision changed.
 */
export function sampleLabel(run: EvalRun = evalRun): string {
  const noun = run.goldenQuestions === 1 ? 'question' : 'questions'
  return run.split === 'holdout'
    ? `${run.goldenQuestions} held-out ${noun}`
    : `${run.goldenQuestions} ${noun}`
}
