import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import GenerationScoreboard from '@/components/projects/GenerationScoreboard'
import {
  formatMetric,
  type GenerationResults,
  type GenerationSection,
} from '@/data/generationResults'

/** A Shipped Arm section, shaped exactly like the generated file. */
function makeSection(overrides: Partial<GenerationSection> = {}): GenerationSection {
  return {
    generatedAt: '2026-10-11T00:00:00+00:00',
    commit: 'abc1234',
    runUrl: 'https://example.test/run/1',
    split: 'holdout',
    arm: 'bm25',
    armLabel: 'Keyword only',
    generationModel: 'gpt-6-luna-2026-08-01',
    reasoningEffort: 'low',
    judge: 'jev-1.13.0',
    splitter: 'gpt-6-luna-2026-08-01',
    corpusChunks: 123,
    questions: 37,
    answerable: 30,
    outOfScope: 7,
    metrics: { factRecall: 0.7, faithfulness: 0.95, declineAccuracy: 1.0 },
    steps: { factRecall: 0.1, faithfulness: 0.05, declineAccuracy: 0.005 },
    costPerAnswerUsd: 0.0002,
    ...overrides,
  }
}

function makeResults(shippedArm: GenerationSection | null = makeSection()): GenerationResults {
  return { schemaVersion: 1, shippedArm, comparison: null }
}

describe('formatMetric', () => {
  it('shows as many decimals as the rounding step carries, and no more', () => {
    // A metric rounded to 0.1 shown as 0.700 would claim a precision nobody measured.
    expect(formatMetric(0.7, 0.1)).toBe('0.7')
    expect(formatMetric(0.95, 0.05)).toBe('0.95')
    expect(formatMetric(0.935, 0.005)).toBe('0.935')
    expect(formatMetric(1, 0.005)).toBe('1.000')
  })

  it('shows a dash for a metric with nothing to measure', () => {
    expect(formatMetric(null, 0.05)).toBe('—')
  })
})

describe('GenerationScoreboard', () => {
  it('renders each published metric at its rounding step', () => {
    render(<GenerationScoreboard results={makeResults()} />)

    const row = (label: string) => screen.getByText(label).closest('tr')!
    expect(within(row('Fact Recall')).getByText('0.7')).toBeInTheDocument()
    expect(within(row('Faithfulness')).getByText('0.95')).toBeInTheDocument()
    expect(within(row('Decline accuracy')).getByText('1.000')).toBeInTheDocument()
  })

  it('names the arm, the model that answered and the Judge that scored it', () => {
    render(<GenerationScoreboard results={makeResults()} />)

    expect(screen.getByText(/Keyword only/)).toBeInTheDocument()
    expect(screen.getByText(/gpt-6-luna-2026-08-01/, { selector: 'dd' })).toBeInTheDocument()
    expect(screen.getByText('jev-1.13.0')).toBeInTheDocument()
  })

  it('shows the cost per answer in dollars', () => {
    render(<GenerationScoreboard results={makeResults()} />)

    expect(screen.getByText('$0.0002')).toBeInTheDocument()
  })

  it('reports the held-out sample it measured', () => {
    render(<GenerationScoreboard results={makeResults()} />)

    expect(
      screen.getByText('37 held-out questions · 7 out of scope · 123 chunks')
    ).toBeInTheDocument()
  })

  it('links to the CI run the numbers came from', () => {
    render(<GenerationScoreboard results={makeResults()} />)

    const link = screen.getByRole('link', { name: /commit abc1234/ })
    expect(link).toHaveAttribute('href', 'https://example.test/run/1')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('names a local run by its commit alone', () => {
    render(<GenerationScoreboard results={makeResults(makeSection({ runUrl: null }))} />)

    expect(screen.queryByRole('link', { name: /commit/ })).not.toBeInTheDocument()
    expect(screen.getByText('commit abc1234')).toBeInTheDocument()
  })

  it('says so when nothing has been published yet, rather than rendering an empty table', () => {
    render(<GenerationScoreboard results={makeResults(null)} />)

    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText(/not been published yet/)).toBeInTheDocument()
  })

  it('renders the published document by default', () => {
    // Whatever CI last published: either the table or the not-yet-published note.
    render(<GenerationScoreboard />)

    expect(screen.getByText('GENERATION EVAL')).toBeInTheDocument()
  })
})
