import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EvalScoreboard from '@/components/projects/EvalScoreboard'
import {
  evalRun,
  leadingArm,
  leadingArmIds,
  sampleLabel,
  shippedArm,
  verdictLine,
  type EvalRun,
} from '@/data/evalResults'

/** A run with two arms, shaped exactly like the generated file. */
function makeRun(overrides: Partial<EvalRun> = {}): EvalRun {
  return {
    schemaVersion: 2,
    generatedAt: '2026-09-04T00:00:00+00:00',
    commit: 'abc1234',
    runUrl: 'https://example.test/run/1',
    corpusChunks: 10,
    goldenQuestions: 20,
    split: 'holdout',
    topK: 5,
    gatingMetric: 'hit@5',
    metricNames: ['hit@5', 'mrr'],
    arms: [
      {
        id: 'bm25',
        label: 'Keyword only',
        description: 'Word matching.',
        technical: 'BM25.',
        shipped: false,
        metrics: { 'hit@5': 1.0, mrr: 0.5 },
      },
      {
        id: 'rerank',
        label: 'Re-ranked',
        description: 'Two-stage.',
        technical: 'Cross-encoder.',
        shipped: true,
        metrics: { 'hit@5': 0.9, mrr: 0.8 },
      },
    ],
    ...overrides,
  }
}

describe('EvalScoreboard', () => {
  it('renders a row for every measured arm', () => {
    render(<EvalScoreboard />)
    for (const arm of evalRun.arms) {
      // Keyed off the description, which is unique per arm — labels need not be.
      const row = screen.getByText(arm.description).closest('tr')!
      expect(within(row).getByText(arm.label)).toBeInTheDocument()
      expect(within(row).getByText(arm.technical)).toBeInTheDocument()
    }
  })

  it('renders a column for every metric the run reports', () => {
    render(<EvalScoreboard />)
    // Column set comes from the data, so a run at a different cutoff needs no code change.
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    for (const metric of evalRun.metricNames) {
      expect(headers).toContain(metric === 'mrr' ? 'MRR' : metric)
    }
  })

  it('shows each score to three decimal places', () => {
    render(<EvalScoreboard />)
    const arm = evalRun.arms[0]
    const row = screen.getByText(arm.description).closest('tr')!
    for (const metric of evalRun.metricNames) {
      expect(within(row).getByText(arm.metrics[metric].toFixed(3))).toBeInTheDocument()
    }
  })

  it('marks the arm that is running in production', () => {
    render(<EvalScoreboard />)
    const shipped = shippedArm()
    if (!shipped) return
    const row = screen.getByText(shipped.description).closest('tr')!
    expect(within(row).getByText('IN PRODUCTION')).toBeInTheDocument()
  })

  it('renders the generated verdict rather than a hand-written claim', () => {
    render(<EvalScoreboard />)
    expect(screen.getByText(verdictLine())).toBeInTheDocument()
  })

  it('reports the corpus and the measured sample', () => {
    render(<EvalScoreboard />)
    expect(
      screen.getByText(`${sampleLabel()} · ${evalRun.corpusChunks} chunks`)
    ).toBeInTheDocument()
  })

  it('says the published questions are held out, so nothing was tuned against them', () => {
    render(<EvalScoreboard />)
    if (evalRun.split !== 'holdout') return
    expect(screen.getByText(/held-out portion of the labelled set/)).toBeInTheDocument()
  })

  it('links to the CI run the numbers came from', () => {
    render(<EvalScoreboard />)
    if (!evalRun.runUrl) return
    const link = screen.getByRole('link', { name: /commit/ })
    expect(link).toHaveAttribute('href', evalRun.runUrl)
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('marks the winning score in each column for screen readers', () => {
    render(<EvalScoreboard />)
    // One marker per arm tied for a column's best, not one per column: two arms
    // currently tie on hit@5, and the sighted reader sees both highlighted.
    const expected = evalRun.metricNames.reduce((n, m) => n + leadingArmIds(m).length, 0)
    expect(screen.getAllByText('(best)')).toHaveLength(expected)
  })
})

describe('leadingArm', () => {
  it('picks the highest scorer per metric independently', () => {
    const run = makeRun()
    expect(leadingArm('hit@5', run.arms).id).toBe('bm25')
    expect(leadingArm('mrr', run.arms).id).toBe('rerank')
  })

  it('agrees with the live data', () => {
    for (const metric of evalRun.metricNames) {
      const max = Math.max(...evalRun.arms.map((a) => a.metrics[metric]))
      expect(leadingArm(metric).metrics[metric]).toBe(max)
    }
  })
})

describe('leadingArmIds', () => {
  it('returns every arm tied for the best score', () => {
    const run = makeRun()
    run.arms[1].metrics['hit@5'] = 1.0
    expect(leadingArmIds('hit@5', run.arms)).toEqual(['bm25', 'rerank'])
  })

  it('returns the single winner when there is no tie', () => {
    expect(leadingArmIds('mrr', makeRun().arms)).toEqual(['rerank'])
  })
})

describe('verdictLine', () => {
  it('names both configurations when the shipped arm is not winning', () => {
    const line = verdictLine(makeRun())
    expect(line).toBe(
      'Production runs Re-ranked. On the current corpus, Keyword only leads on hit@5 ' +
        '(1.000 vs 0.900).'
    )
  })

  it('heals into a statement of agreement when the shipped arm wins', () => {
    // The reason the sentence is generated: fixing the architecture fixes the prose.
    const run = makeRun()
    run.arms[1].metrics['hit@5'] = 1.0
    run.arms[0].metrics['hit@5'] = 0.8
    expect(verdictLine(run)).toBe('Production runs Re-ranked, which also leads on hit@5 (1.000).')
  })

  it('calls a tie a tie rather than a win for production', () => {
    // The shipped arm is listed first, so a positional tie-break would report every
    // tie as a lead. Production must not be flattered by list order.
    const run = makeRun()
    run.arms[1].metrics['hit@5'] = 1.0
    expect(verdictLine(run)).toBe(
      'Production runs Re-ranked, tied for the lead on hit@5 (1.000) with Keyword only.'
    )
  })

  it('says so plainly when no arm is flagged as shipped', () => {
    const run = makeRun()
    run.arms.forEach((a) => (a.shipped = false))
    expect(verdictLine(run)).toContain('No arm is flagged as shipped')
  })

  it('tolerates an arm missing a metric the run reports', () => {
    const run = makeRun()
    delete run.arms[0].metrics['hit@5']
    expect(() => verdictLine(run)).not.toThrow()
    expect(leadingArm('hit@5', run.arms).id).toBe('rerank')
  })
})

describe('sampleLabel', () => {
  it('says a held-out run is held out', () => {
    expect(sampleLabel(makeRun())).toBe('20 held-out questions')
  })

  it('claims nothing extra for a run over the whole set', () => {
    // Which portion gets published is the harness's decision; the page must follow it
    // rather than assert "held-out" forever.
    expect(sampleLabel(makeRun({ split: 'all' }))).toBe('20 questions')
  })
})

describe('the generated results file', () => {
  it('publishes the portion no configuration was chosen against', () => {
    expect(evalRun.split).toBe('holdout')
  })

  it('flags exactly one arm as shipped', () => {
    expect(evalRun.arms.filter((a) => a.shipped)).toHaveLength(1)
  })

  it('gives every arm a score for every reported metric', () => {
    for (const arm of evalRun.arms) {
      for (const metric of evalRun.metricNames) {
        expect(typeof arm.metrics[metric]).toBe('number')
      }
    }
  })

  it('carries both registers of description for every arm', () => {
    for (const arm of evalRun.arms) {
      expect(arm.description.length).toBeGreaterThan(0)
      expect(arm.technical.length).toBeGreaterThan(0)
      expect(arm.description).not.toBe(arm.technical)
    }
  })
})
