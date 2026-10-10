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
  type EvalArm,
  type EvalRun,
} from '@/data/evalResults'

/** A run with two arms, shaped exactly like the generated file. */
function makeRun(overrides: Partial<EvalRun> = {}): EvalRun {
  return {
    schemaVersion: 4,
    generatedAt: '2026-09-04T00:00:00+00:00',
    commit: 'abc1234',
    runUrl: 'https://example.test/run/1',
    corpusChunks: 10,
    goldenQuestions: 20,
    split: 'holdout',
    topK: 5,
    gatingMetric: 'hit@5',
    categories: ['direct', 'paraphrase'],
    categoryCounts: { direct: 15, paraphrase: 5 },
    metricNames: ['hit@5', 'mrr'],
    arms: [
      {
        id: 'bm25',
        label: 'Keyword only',
        description: 'Word matching.',
        technical: 'BM25.',
        shipped: false,
        metrics: { 'hit@5': 1.0, mrr: 0.5 },
        byCategory: {
          direct: { 'hit@5': 1.0, mrr: 0.5 },
          paraphrase: { 'hit@5': 0.6, mrr: 0.3 },
        },
        mrrInterval: [0.35, 0.65],
        vsShipped: { won: 4, lost: 2, outcome: 'indistinguishable' },
        vsShippedByCategory: {
          direct: { won: 4, lost: 0, outcome: 'indistinguishable' },
          paraphrase: { won: 0, lost: 2, outcome: 'indistinguishable' },
        },
      },
      {
        id: 'rerank',
        label: 'Re-ranked',
        description: 'Two-stage.',
        technical: 'Cross-encoder.',
        shipped: true,
        metrics: { 'hit@5': 0.9, mrr: 0.8 },
        byCategory: {
          direct: { 'hit@5': 0.9, mrr: 0.8 },
          paraphrase: { 'hit@5': 0.95, mrr: 0.85 },
        },
        mrrInterval: [0.7, 0.9],
        vsShipped: null,
        vsShippedByCategory: null,
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

  it('renders interactive category tabs for all queries and each category', () => {
    render(<EvalScoreboard />)
    const allTab = screen.getByRole('tab', { name: /all queries/i })
    const directTab = screen.getByRole('tab', { name: /direct/i })
    const paraphraseTab = screen.getByRole('tab', { name: /paraphrase/i })

    expect(allTab).toBeInTheDocument()
    expect(directTab).toBeInTheDocument()
    expect(paraphraseTab).toBeInTheDocument()
    expect(allTab).toHaveAttribute('aria-selected', 'true')
    expect(directTab).toHaveAttribute('aria-selected', 'false')
    expect(paraphraseTab).toHaveAttribute('aria-selected', 'false')
  })

  it('switches displayed metrics when clicking a category tab', async () => {
    const { userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    render(<EvalScoreboard />)

    const paraphraseTab = screen.getByRole('tab', { name: /paraphrase/i })
    await user.click(paraphraseTab)

    expect(paraphraseTab).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /all queries/i })).toHaveAttribute(
      'aria-selected',
      'false'
    )

    for (const arm of evalRun.arms) {
      const row = screen.getByText(arm.description).closest('tr')!
      for (const metric of evalRun.metricNames) {
        const catVal = arm.byCategory['paraphrase']?.[metric]
        if (catVal !== undefined) {
          expect(within(row).getByText(catVal.toFixed(3))).toBeInTheDocument()
        }
      }
    }
  })
})

describe('EvalScoreboard won/lost column', () => {
  it('shows questions won and lost against production for every other arm', () => {
    render(<EvalScoreboard run={makeRun()} />)
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toContain('VS PRODUCTION')

    const bm25 = screen.getByText('Word matching.').closest('tr')!
    expect(within(bm25).getByText('4 won · 2 lost')).toBeInTheDocument()
    // The shipped arm is the reference, not a contestant against itself.
    const shipped = screen.getByText('Two-stage.').closest('tr')!
    expect(within(shipped).getByText('—')).toBeInTheDocument()
  })

  it("switches to the category's own counts with the category filter", async () => {
    const { userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    render(<EvalScoreboard run={makeRun()} />)

    await user.click(screen.getByRole('tab', { name: /paraphrase/i }))

    const bm25 = screen.getByText('Word matching.').closest('tr')!
    expect(within(bm25).getByText('0 won · 2 lost')).toBeInTheDocument()
  })

  it('does not publish the MRR interval on the page', () => {
    // ADR-0006: bootstrap intervals belong to docs/evaluation.md only.
    render(<EvalScoreboard run={makeRun()} />)
    expect(screen.queryByText(/0\.350/)).not.toBeInTheDocument()
    expect(screen.queryByText(/95%/)).not.toBeInTheDocument()
  })
})

describe('leadingArm', () => {
  it('picks the highest scorer per metric independently', () => {
    const run = makeRun()
    expect(leadingArm('hit@5', run.arms).id).toBe('bm25')
    expect(leadingArm('mrr', run.arms).id).toBe('rerank')
  })

  it('picks highest scorer within a specific category', () => {
    const run = makeRun()
    expect(leadingArm('hit@5', run.arms, 'paraphrase').id).toBe('rerank')
    expect(leadingArm('hit@5', run.arms, 'direct').id).toBe('bm25')
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

  it('returns arm ids winning within a category', () => {
    const run = makeRun()
    expect(leadingArmIds('hit@5', run.arms, 'paraphrase')).toEqual(['rerank'])
  })
})

/** A third arm, so a verdict can name arms on both sides of the shipped one. */
function withDense(run: EvalRun, vsShipped: EvalArm['vsShipped']): EvalRun {
  run.arms.push({
    ...run.arms[0],
    id: 'dense',
    label: 'Meaning only',
    description: 'Semantic matching.',
    vsShipped,
  })
  return run
}

describe('verdictLine', () => {
  it('says no arm is distinguishable, and names the sample, when the split is balanced', () => {
    // Keyword only scores 0.100 higher on hit@5, which the old verdict called a lead.
    // Four questions won and two lost is well inside sampling noise.
    expect(verdictLine(makeRun())).toBe(
      'Production runs Re-ranked. Across the 20 held-out questions, no other arm is ' +
        'distinguishable from it on hit@5.'
    )
  })

  it('names an arm that is distinguishably ahead, with its won/lost counts', () => {
    const run = makeRun()
    run.arms[0].vsShipped = { won: 8, lost: 0, outcome: 'ahead' }
    expect(verdictLine(run)).toBe(
      'Production runs Re-ranked. Across the 20 held-out questions, Keyword only ' +
        '(won 8, lost 0) is distinguishably ahead of it on hit@5.'
    )
  })

  it('names an arm that is distinguishably behind', () => {
    const run = makeRun()
    run.arms[0].vsShipped = { won: 1, lost: 9, outcome: 'behind' }
    expect(verdictLine(run)).toBe(
      'Production runs Re-ranked. Across the 20 held-out questions, Keyword only ' +
        '(won 1, lost 9) is distinguishably behind it on hit@5.'
    )
  })

  it('names arms on both sides in one sentence', () => {
    const run = withDense(makeRun(), { won: 0, lost: 7, outcome: 'behind' })
    run.arms[0].vsShipped = { won: 8, lost: 0, outcome: 'ahead' }
    expect(verdictLine(run)).toBe(
      'Production runs Re-ranked. Across the 20 held-out questions, Keyword only ' +
        '(won 8, lost 0) is distinguishably ahead of it on hit@5, and Meaning only ' +
        '(won 0, lost 7) is behind it.'
    )
  })

  it('joins several arms on the same side', () => {
    const run = withDense(makeRun(), { won: 6, lost: 0, outcome: 'ahead' })
    run.arms[0].vsShipped = { won: 8, lost: 0, outcome: 'ahead' }
    expect(verdictLine(run)).toBe(
      'Production runs Re-ranked. Across the 20 held-out questions, Keyword only ' +
        '(won 8, lost 0) and Meaning only (won 6, lost 0) are distinguishably ahead of it ' +
        'on hit@5.'
    )
  })

  it("follows the category filter, using that category's own disagreements", () => {
    const run = makeRun()
    run.arms[0].vsShippedByCategory!.direct = { won: 7, lost: 0, outcome: 'ahead' }
    expect(verdictLine(run, 'direct')).toBe(
      'Production runs Re-ranked. Across the 15 held-out direct questions, Keyword only ' +
        '(won 7, lost 0) is distinguishably ahead of it on hit@5.'
    )
    expect(verdictLine(run, 'paraphrase')).toBe(
      'Production runs Re-ranked. Across the 5 held-out paraphrase questions, no other arm ' +
        'is distinguishable from it on hit@5.'
    )
  })

  it('names a run over the whole set without calling it held out', () => {
    expect(verdictLine(makeRun({ split: 'all' }))).toContain('Across all 20 questions,')
  })

  it('says so plainly when no arm is flagged as shipped', () => {
    const run = makeRun()
    run.arms.forEach((a) => (a.shipped = false))
    expect(verdictLine(run)).toBe(
      'No arm is flagged as shipped, so no arm is compared against production.'
    )
  })

  it('says so when the shipped arm is the only one measured', () => {
    const run = makeRun()
    run.arms = [run.arms[1]]
    expect(verdictLine(run)).toBe('Production runs Re-ranked. No other arm was measured.')
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

  it('reports category-specific count when filtering by category', () => {
    expect(sampleLabel(makeRun(), 'paraphrase')).toBe('5 held-out paraphrase questions')
    expect(sampleLabel(makeRun(), 'direct')).toBe('15 held-out direct questions')
  })

  it('singularizes question when category count is 1', () => {
    expect(
      sampleLabel(makeRun({ categoryCounts: { direct: 19, paraphrase: 1 } }), 'paraphrase')
    ).toBe('1 held-out paraphrase question')
  })
})

describe('the generated results file', () => {
  it('is schemaVersion 4', () => {
    expect(evalRun.schemaVersion).toBe(4)
  })

  it('compares every arm but the shipped one against production', () => {
    for (const arm of evalRun.arms) {
      if (arm.shipped) {
        expect(arm.vsShipped).toBeNull()
        continue
      }
      expect(arm.vsShipped).toEqual({
        won: expect.any(Number),
        lost: expect.any(Number),
        outcome: expect.stringMatching(/^(ahead|behind|indistinguishable)$/),
      })
      for (const category of evalRun.categories) {
        expect(arm.vsShippedByCategory?.[category]).toBeDefined()
      }
    }
  })

  it('publishes the portion no configuration was chosen against', () => {
    expect(evalRun.split).toBe('holdout')
  })

  it('publishes categories including direct, paraphrase, and conceptual', () => {
    expect(evalRun.categories).toContain('direct')
    expect(evalRun.categories).toContain('paraphrase')
    expect(evalRun.categories).toContain('conceptual')
  })

  it('publishes categoryCounts matching the holdout split', () => {
    expect(evalRun.categoryCounts).toBeDefined()
    expect(evalRun.categoryCounts?.direct).toBe(22)
    expect(evalRun.categoryCounts?.paraphrase).toBe(5)
    expect(evalRun.categoryCounts?.conceptual).toBe(6)
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

  it('carries per-category metrics for every arm', () => {
    for (const arm of evalRun.arms) {
      expect(arm.byCategory).toBeDefined()
      for (const category of evalRun.categories) {
        expect(arm.byCategory[category]).toBeDefined()
        for (const metric of evalRun.metricNames) {
          expect(typeof arm.byCategory[category][metric]).toBe('number')
        }
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
