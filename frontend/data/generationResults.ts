/**
 * The most recent published measurement of the chatbot's answers.
 *
 * `generationResults.json` is GENERATED. The `Generation gate` CI job answers the golden
 * questions, has a pinned Judge score the answers, and commits this file on pushes to
 * `main` — see backend/eval/publish_generation.py and docs/adr/0007. Editing it by hand
 * publishes a number nothing measured.
 *
 * It has two sections with their own provenance, because they come from different runs:
 * `shippedArm` (the gate on `main`) and `comparison` (the manual comparison run). A
 * section is `null` until its run has published.
 */
import results from './generationResults.json'

/** The published metrics, in display order. */
export type GenerationMetric = 'factRecall' | 'faithfulness' | 'declineAccuracy'

export interface GenerationSection {
  generatedAt: string
  /** Commit the run was measured on. */
  commit: string
  /** The CI job that produced the numbers, when a CI run produced them. */
  runUrl: string | null
  /** Always `holdout`: decisions are made on `dev`, and only held-out results publish. */
  split: string
  /** Retrieval Arm the answers were written from. */
  arm: string
  armLabel: string
  /** The model ID the provider reported answering with. */
  generationModel: string
  reasoningEffort: string | null
  /** The pinned Judge version that scored the answers. */
  judge: string
  /** The model that split answer sentences into claims for the Judge. */
  splitter: string
  corpusChunks: number
  questions: number
  answerable: number
  outOfScope: number
  /** Each rounded to its step in `steps`. `null` when there was nothing to measure. */
  metrics: Record<GenerationMetric, number | null>
  /** The rounding step of each metric, from the run-to-run spread study. */
  steps: Record<GenerationMetric, number>
  /** Mean billed cost per answer in USD, to one significant figure. */
  costPerAnswerUsd: number | null
}

export interface GenerationResults {
  schemaVersion: number
  shippedArm: GenerationSection | null
  comparison: GenerationSection | null
}

export const generationResults: GenerationResults = results as GenerationResults

/**
 * A metric with as many decimals as its rounding step carries.
 *
 * A metric rounded to 0.1 shown as `0.700` would claim a precision nobody measured.
 */
export function formatMetric(value: number | null, step: number): string {
  if (value === null) return '—'
  return value.toFixed(step.toString().split('.')[1]?.length ?? 0)
}
