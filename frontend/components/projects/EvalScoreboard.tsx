import { evalRun, leadingArm, metricLabel, verdictLine, type EvalArm } from '@/data/evalResults'

function format(value: number | undefined): string {
  return value === undefined ? '—' : value.toFixed(3)
}

/**
 * The measured run, rendered.
 *
 * Every claim here is derived from `evalResults.json`: which arm leads each column, and
 * the verdict line beneath the table. Nothing about the outcome is written by hand, so the
 * component cannot contradict its own numbers and needs no edit when the numbers move, an
 * arm is added, or the shipped configuration changes.
 */
export default function EvalScoreboard() {
  const metrics = evalRun.metricNames
  const winners = Object.fromEntries(metrics.map((m) => [m, leadingArm(m).id]))

  return (
    <figure className="my-8">
      <div className="overflow-hidden rounded-xl border border-white/[0.06] shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
        {/* Header strip */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-white/[0.06] bg-white/[0.03] px-4 py-2.5">
          <span className="font-mono text-[8px] tracking-[0.3em] text-[#8a8f98]/40">
            RETRIEVAL EVAL
          </span>
          <span className="ml-auto font-mono text-[9px] tracking-widest text-[#8a8f98]">
            {evalRun.goldenQuestions} questions · {evalRun.corpusChunks} chunks
          </span>
        </div>

        {/* Wide content scrolls inside its own container rather than the page */}
        <div className="overflow-x-auto bg-[#0a0a0c]">
          <table className="w-full min-w-[34rem] border-collapse text-left">
            <caption className="sr-only">
              Retrieval quality by pipeline configuration, measured on {evalRun.goldenQuestions}{' '}
              labelled questions.
            </caption>
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th
                  scope="col"
                  className="px-4 py-3 font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                >
                  CONFIGURATION
                </th>
                {metrics.map((m) => (
                  <th
                    key={m}
                    scope="col"
                    className="px-4 py-3 text-right font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                  >
                    {metricLabel(m)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {evalRun.arms.map((arm: EvalArm) => (
                <tr
                  key={arm.id}
                  className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]"
                >
                  <th scope="row" className="px-4 py-3 align-top font-normal">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-sm text-[#ededef]">{arm.label}</span>
                      {arm.shipped && (
                        <span className="rounded-full border border-[#0ea5e9]/30 px-2 py-px font-mono text-[8px] tracking-widest text-[#0ea5e9]">
                          IN PRODUCTION
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-[#8a8f98]">
                      {arm.description}
                    </span>
                    <span className="mt-1 block font-mono text-[10px] leading-relaxed text-[#8a8f98]/50">
                      {arm.technical}
                    </span>
                  </th>
                  {metrics.map((m) => {
                    const isBest = winners[m] === arm.id
                    return (
                      <td
                        key={m}
                        className={`px-4 py-3 text-right align-top font-mono text-sm tabular-nums ${
                          isBest ? 'text-[#0ea5e9]' : 'text-[#8a8f98]'
                        }`}
                      >
                        {format(arm.metrics[m])}
                        {isBest && <span className="sr-only"> (best)</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* The verdict is computed from the table above it, never typed. */}
        <div className="border-t border-white/[0.06] bg-white/[0.03] px-4 py-3">
          <p className="text-sm leading-relaxed text-[#ededef]">{verdictLine()}</p>
        </div>
      </div>

      <figcaption className="mt-3 text-xs leading-relaxed text-[#8a8f98]">
        Best score per column in blue. This table and the sentence above it are generated from the
        evaluation harness — measured at{' '}
        {evalRun.runUrl ? (
          <a
            href={evalRun.runUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#0ea5e9] underline decoration-[#0ea5e9]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#0ea5e9]"
          >
            commit {evalRun.commit}
          </a>
        ) : (
          <span className="font-mono">commit {evalRun.commit}</span>
        )}
        .
      </figcaption>
    </figure>
  )
}
