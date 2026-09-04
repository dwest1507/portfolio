import { evalRun, bestArmId, type EvalArm } from '@/data/evalResults'

const METRICS = [
  { key: 'hitAt5', label: 'hit@5', hint: 'Any relevant chunk in the top 5' },
  { key: 'recallAt5', label: 'recall@5', hint: 'Share of all relevant chunks in the top 5' },
  { key: 'mrr', label: 'MRR', hint: 'Mean reciprocal rank of the first relevant chunk' },
  { key: 'ndcgAt5', label: 'nDCG@5', hint: 'Rank-discounted gain' },
] as const

type MetricKey = (typeof METRICS)[number]['key']

function format(value: number): string {
  return value.toFixed(3)
}

export default function EvalScoreboard() {
  const winners: Record<MetricKey, string> = {
    hitAt5: bestArmId('hitAt5'),
    recallAt5: bestArmId('recallAt5'),
    mrr: bestArmId('mrr'),
    ndcgAt5: bestArmId('ndcgAt5'),
  }

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
                {METRICS.map((m) => (
                  <th
                    key={m.key}
                    scope="col"
                    title={m.hint}
                    className="px-4 py-3 text-right font-mono text-[9px] tracking-widest text-[#8a8f98]/60"
                  >
                    {m.label}
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
                    <span className="block text-sm text-[#ededef]">{arm.label}</span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-[#8a8f98]">
                      {arm.description}
                    </span>
                  </th>
                  {METRICS.map((m) => {
                    const isBest = winners[m.key] === arm.id
                    return (
                      <td
                        key={m.key}
                        className={`px-4 py-3 text-right align-top font-mono text-sm tabular-nums ${
                          isBest ? 'text-[#0ea5e9]' : 'text-[#8a8f98]'
                        }`}
                      >
                        {format(arm[m.key])}
                        {isBest && <span className="sr-only"> (best)</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <figcaption className="mt-3 text-xs leading-relaxed text-[#8a8f98]">
        Best score per column in blue. Measured on{' '}
        <a
          href={evalRun.runUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#0ea5e9] underline decoration-[#0ea5e9]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#0ea5e9]"
        >
          CI run at {evalRun.commit}
        </a>
        .
      </figcaption>
    </figure>
  )
}
