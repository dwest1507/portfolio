import { findings, type Finding } from '@/data/evalFindings'

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  })
}

function MetricMove({ finding }: { finding: Finding }) {
  if (!finding.move) return null
  const { metric, before, after, arm } = finding.move
  return (
    <p className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] text-[#8a8f98]">
      <span className="text-[#8a8f98]/60">{arm}</span>
      <span className="text-[#8a8f98]/60">{metric}</span>
      <span className="tabular-nums">{before.toFixed(3)}</span>
      <span aria-hidden className="text-[#8a8f98]/40">
        →
      </span>
      <span className="sr-only">to</span>
      <span className="text-[#0ea5e9] tabular-nums">{after.toFixed(3)}</span>
    </p>
  )
}

/**
 * The append-only record of what the evaluation changed.
 *
 * Unlike the scoreboard, this content is hand-written — a finding is a judgement, not a
 * derivation. It is rendered from data rather than MDX so it stays out of the retrieval
 * corpus; see docs/adr/0002-findings-log-outside-the-corpus.md.
 */
export default function FindingsLog() {
  return (
    <section className="my-8" aria-label="Findings log">
      <ol className="space-y-px">
        {findings.map((finding) => (
          <li
            key={finding.id}
            className="border-l-2 border-white/[0.06] py-4 pl-5 transition-colors duration-150 hover:border-[#0ea5e9]/40"
          >
            <p className="font-mono text-[9px] tracking-widest text-[#8a8f98]/50">
              <time dateTime={finding.date}>{formatDate(finding.date)}</time>
            </p>
            <h4 className="mt-1.5 text-sm font-medium text-[#ededef]">{finding.title}</h4>
            <p className="mt-2 text-sm leading-7 text-[#8a8f98]">{finding.observed}</p>
            <p className="mt-2 text-sm leading-7 text-[#8a8f98]">
              <span className="text-[#ededef]">What changed: </span>
              {finding.changed}
            </p>
            <MetricMove finding={finding} />
            {finding.href && (
              <p className="mt-3">
                <a
                  href={finding.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#0ea5e9] underline decoration-[#0ea5e9]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#0ea5e9]"
                >
                  Full account ↗
                </a>
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
