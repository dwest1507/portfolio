import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EvalScoreboard from '@/components/projects/EvalScoreboard'
import { evalRun, bestArmId } from '@/data/evalResults'

describe('EvalScoreboard', () => {
  it('renders a row for every measured arm', () => {
    render(<EvalScoreboard />)
    for (const arm of evalRun.arms) {
      // Keyed off the description, which is unique per arm — labels are not
      // ("Hybrid" is a prefix of "Hybrid + re-rank").
      const row = screen.getByText(arm.description).closest('tr')!
      expect(within(row).getByText(arm.label)).toBeInTheDocument()
    }
  })

  it('renders every metric column', () => {
    render(<EvalScoreboard />)
    for (const label of ['hit@5', 'recall@5', 'MRR', 'nDCG@5']) {
      expect(screen.getByRole('columnheader', { name: label })).toBeInTheDocument()
    }
  })

  it('shows each score to three decimal places', () => {
    render(<EvalScoreboard />)
    const bm25 = evalRun.arms.find((a) => a.id === 'bm25')!
    const row = screen.getByText(bm25.description).closest('tr')!
    expect(within(row).getByText('1.000')).toBeInTheDocument()
    expect(within(row).getByText('0.730')).toBeInTheDocument()
  })

  it('reports the corpus and golden set size', () => {
    render(<EvalScoreboard />)
    expect(
      screen.getByText(`${evalRun.goldenQuestions} questions · ${evalRun.corpusChunks} chunks`)
    ).toBeInTheDocument()
  })

  it('links to the CI run the numbers came from', () => {
    render(<EvalScoreboard />)
    const link = screen.getByRole('link', { name: /CI run at/ })
    expect(link).toHaveAttribute('href', evalRun.runUrl)
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('marks the winning score in each column for screen readers', () => {
    render(<EvalScoreboard />)
    // One "(best)" marker per metric column.
    expect(screen.getAllByText('(best)')).toHaveLength(4)
  })
})

describe('bestArmId', () => {
  it('picks the highest scorer for a metric', () => {
    // BM25 currently leads every metric; assert against the data rather than
    // hardcoding, so this keeps working when the numbers are refreshed.
    for (const metric of ['hitAt5', 'recallAt5', 'mrr', 'ndcgAt5'] as const) {
      const winner = evalRun.arms.find((a) => a.id === bestArmId(metric))!
      const max = Math.max(...evalRun.arms.map((a) => a[metric]))
      expect(winner[metric]).toBe(max)
    }
  })
})
