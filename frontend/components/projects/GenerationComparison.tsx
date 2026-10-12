import type { VsShipped } from '@/data/evalResults'
import {
  formatMetric,
  GENERATION_METRICS,
  generationResults,
  type GenerationResults,
} from '@/data/generationResults'

/** Only a difference beyond sampling noise gets a badge (ADR-0006). */
function OutcomeBadge({ vs }: { vs: VsShipped }) {
  if (vs.outcome === 'indistinguishable') return null
  const ahead = vs.outcome === 'ahead'
  return (
    <span
      className={`ml-2 rounded-full border px-1.5 py-px font-mono text-[8px] tracking-widest ${
        ahead ? 'border-[#22c55e]/30 text-[#22c55e]' : 'border-[#f97316]/30 text-[#f97316]'
      }`}
    >
      {ahead ? 'AHEAD' : 'BEHIND'}
    </span>
  )
}

/**
 * Every Candidate Arm's answers, from the manual comparison run (ADR-0009).
 *
 * Renders the Comparison section of `generationResults.json`, which a different run
 * produces from the Shipped Arm section, so it carries its own provenance and is never
 * merged into that table. Each row shows the Arm's held-out scores and, under each, the
 * pairs it won and lost against the Shipped Arm; a badge appears only when that split is
 * too lopsided to be chance.
 *
 * `results` defaults to the published document; it is a prop only so tests can render
 * fixtures.
 */
export default function GenerationComparison({
  results = generationResults,
}: {
  results?: GenerationResults
}) {
  const run = results.comparison

  return (
    <figure className="my-8">
      <div className="overflow-hidden rounded-xl border border-white/[0.06] shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-white/[0.06] bg-white/[0.03] px-4 py-2.5">
          <span className="font-mono text-[8px] tracking-[0.3em] text-[#8a8f98]/40">
            ARM COMPARISON
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
              <table className="w-full min-w-[36rem] border-collapse text-left">
                <caption className="sr-only">
                  Answer quality of each retrieval configuration that could ship, measured on{' '}
                  {run.questions} held-out questions and compared with the one in production.
                </caption>
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th
                      scope="col"
                      className="px-4 py-3 font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                    >
                      RETRIEVAL
                    </th>
                    {GENERATION_METRICS.map((metric) => (
                      <th
                        key={metric.id}
                        scope="col"
                        title={metric.description}
                        className="px-4 py-3 text-right font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                      >
                        {metric.label.toUpperCase()}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {run.arms.map((arm) => (
                    <tr
                      key={arm.arm}
                      className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]"
                    >
                      <th scope="row" className="px-4 py-3 align-top font-normal">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-sm text-[#ededef]">{arm.armLabel}</span>
                          {arm.shipped && (
                            <span className="rounded-full border border-[#0ea5e9]/30 px-2 py-px font-mono text-[8px] tracking-widest text-[#0ea5e9]">
                              IN PRODUCTION
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block font-mono text-[10px] text-[#8a8f98]">
                          {arm.arm}
                        </span>
                      </th>
                      {GENERATION_METRICS.map((metric) => {
                        const vs = arm.vsShipped?.[metric.id]
                        return (
                          <td
                            key={metric.id}
                            className="px-4 py-3 text-right align-top font-mono text-sm text-[#ededef] tabular-nums"
                          >
                            <span>
                              {formatMetric(arm.metrics[metric.id], run.steps[metric.id])}
                            </span>
                            {vs && (
                              <span className="mt-0.5 flex items-center justify-end text-[10px] text-[#8a8f98]">
                                <span>
                                  {vs.won} won · {vs.lost} lost
                                </span>
                                <OutcomeBadge vs={vs} />
                              </span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-white/[0.06] bg-white/[0.03] px-4 py-3 text-xs sm:grid-cols-2">
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">MODEL</dt>
                <dd className="font-mono text-[#ededef]">{run.generationModel}</dd>
              </div>
              <div>
                <dt className="font-mono text-[9px] tracking-widest text-[#8a8f98]/60">JUDGE</dt>
                <dd className="font-mono text-[#ededef]">{run.judge}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="bg-[#0a0a0c] px-4 py-6 text-sm text-[#8a8f98]">
            No comparison has been published yet. It appears here after the comparison run is next
            dispatched on <span className="font-mono">main</span>.
          </p>
        )}
      </div>

      {run && (
        <figcaption className="mt-3 text-xs leading-relaxed text-[#8a8f98]">
          A separate, manually triggered run: every configuration that could ship answers the same
          held-out questions with the same model and judge. Under each score are the questions it
          got right that production got wrong, and the reverse; a configuration is only called ahead
          or behind when that split is too lopsided to be chance. The decision is made on a
          different set of questions, so these numbers confirm it rather than make it. Measured at{' '}
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
