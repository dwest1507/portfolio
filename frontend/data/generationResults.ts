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
import type { Eligibility, VsShipped } from './evalResults'
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

/** One Candidate Arm's held-out answers in the comparison run. */
export interface ComparisonRow {
  arm: string
  armLabel: string
  /** Always `candidate`: Reference Arms are never run through generation (ADR-0007). */
  eligibility: Eligibility
  /** True for the Shipped Arm, which every other row is compared with. */
  shipped: boolean
  /** Each rounded to its step in the section's `steps`. */
  metrics: Record<GenerationMetric, number | null>
  costPerAnswerUsd: number | null
  /**
   * Pairs won and lost against the Shipped Arm on each metric, with the sign-test outcome
   * (ADR-0006). `null` for the Shipped Arm itself.
   */
  vsShipped: Record<GenerationMetric, VsShipped> | null
}

/**
 * The manual comparison run of every Candidate Arm through generation (ADR-0009).
 *
 * Its provenance is its own: it is a different run from the Shipped Arm section's.
 */
export interface ComparisonSection {
  generatedAt: string
  commit: string
  runUrl: string | null
  /** Always `holdout`: the decision is made on `dev`, which stays in the CI artifact. */
  split: string
  /** The Arm every row is compared with. */
  shippedArm: string
  generationModel: string
  reasoningEffort: string | null
  judge: string
  splitter: string
  corpusChunks: number
  questions: number
  answerable: number
  outOfScope: number
  steps: Record<GenerationMetric, number>
  arms: ComparisonRow[]
}

export interface GenerationResults {
  schemaVersion: number
  shippedArm: GenerationSection | null
  comparison: ComparisonSection | null
}

export const generationResults: GenerationResults = results as GenerationResults

/** The published metrics, in display order, with what each measures for a page reader. */
export const GENERATION_METRICS: { id: GenerationMetric; label: string; description: string }[] = [
  {
    id: 'faithfulness',
    label: 'Faithfulness',
    description: 'Share of factual sentences in an answer that the retrieved text supports.',
  },
  {
    id: 'declineAccuracy',
    label: 'Decline accuracy',
    description:
      'Share of questions handled correctly: answered when the documents cover them, declined when they do not.',
  },
  {
    id: 'factRecall',
    label: 'Fact Recall',
    description: 'Share of the facts a complete answer should contain that the answer conveyed.',
  },
]

/**
 * A metric with as many decimals as its rounding step carries.
 *
 * A metric rounded to 0.1 shown as `0.700` would claim a precision nobody measured.
 */
export function formatMetric(value: number | null, step: number): string {
  if (value === null) return '—'
  return value.toFixed(step.toString().split('.')[1]?.length ?? 0)
}
