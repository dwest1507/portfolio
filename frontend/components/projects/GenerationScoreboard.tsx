import {
  formatMetric,
  generationResults,
  type GenerationMetric,
  type GenerationResults,
} from '@/data/generationResults'

const METRICS: { id: GenerationMetric; label: string; description: string }[] = [
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

/** Faithfulness and Decline accuracy fail the build below their Floors; Fact Recall does not. */
const GATED = new Set<GenerationMetric>(['faithfulness', 'declineAccuracy'])

function dollars(value: number | null): string {
  return value === null ? '—' : `$${value}`
}

/**
 * The chatbot's answers, as measured by the generation gate on `main`.
 *
 * Renders the Shipped Arm section of `generationResults.json`: every number is generated
 * by CI and rounded to the step its run-to-run noise allows. The comparison section is a
 * different run with its own provenance and is not mixed into this table.
 *
 * `results` defaults to the published document; it is a prop only so tests can render
 * fixtures.
 */
export default function GenerationScoreboard({
  results = generationResults,
}: {
  results?: GenerationResults
}) {
  const run = results.shippedArm

  return (
    <figure className="my-8">
      <div className="overflow-hidden rounded-xl border border-white/[0.06] shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-white/[0.06] bg-white/[0.03] px-4 py-2.5">
          <span className="font-mono text-[8px] tracking-[0.3em] text-[#8a8f98]/40">
            GENERATION EVAL
          </span>
          {run && (
            <span className="font-mono text-[9px] tracking-widest text-[#8a8f98]">
              {run.questions} held-out questions · {run.outOfScope} out of scope ·{' '}
              {run.corpusChunks} chunks
            </span>
          )}
        </div>

        {run ? (
          <>
            <div className="overflow-x-auto bg-[#0a0a0c]">
              <table className="w-full min-w-[28rem] border-collapse text-left">
                <caption className="sr-only">
                  Answer quality of the chatbot in production, measured on {run.questions} held-out
                  questions.
                </caption>
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th
                      scope="col"
                      className="px-4 py-3 font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                    >
                      METRIC
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-right font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                    >
                      SCORE
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {METRICS.map((metric) => (
                    <tr
                      key={metric.id}
                      className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]"
                    >
                      <th scope="row" className="px-4 py-3 align-top font-normal">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-sm text-[#ededef]">{metric.label}</span>
                          {GATED.has(metric.id) && (
                            <span className="rounded-full border border-[#0ea5e9]/30 px-2 py-px font-mono text-[8px] tracking-widest text-[#0ea5e9]">
                              GATED
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block text-xs leading-relaxed text-[#8a8f98]">
                          {metric.description}
                        </span>
                      </th>
                      <td className="px-4 py-3 text-right align-top font-mono text-sm text-[#ededef] tabular-nums">
                        {formatMetric(run.metrics[metric.id], run.steps[metric.id])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-white/[0.06] bg-white/[0.03] px-4 py-3 text-xs sm:grid-cols-2">
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">
                  RETRIEVAL
                </dt>
                <dd className="text-[#ededef]">{run.armLabel}</dd>
              </div>
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">MODEL</dt>
                <dd className="font-mono text-[#ededef]">{run.generationModel}</dd>
              </div>
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">JUDGE</dt>
                <dd className="font-mono text-[#ededef]">{run.judge}</dd>
              </div>
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">
                  COST PER ANSWER
                </dt>
                <dd className="font-mono text-[#ededef]">{dollars(run.costPerAnswerUsd)}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="bg-[#0a0a0c] px-4 py-6 text-sm text-[#8a8f98]">
            Answer quality has not been published yet. It appears here after the generation gate
            next runs on <span className="font-mono">main</span>.
          </p>
        )}
      </div>

      {run && (
        <figcaption className="mt-3 text-xs leading-relaxed text-[#8a8f98]">
          Generated by the evaluation harness: each answer is scored by a separate, pinned judge
          model, not by me. Faithfulness and Decline accuracy fail the build if they drop below
          their floors. Each score is rounded to the step its run-to-run noise allows, so a number
          moves only when the answers really changed. Measured at{' '}
          {run.runUrl ? (
            <a
              href={run.runUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#0ea5e9] underline decoration-[#0ea5e9]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#0ea5e9]"
            >
              commit {run.commit}
            </a>
          ) : (
            <span className="font-mono">commit {run.commit}</span>
          )}
          .
        </figcaption>
      )}
    </figure>
  )
}
