import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import GenerationComparison from '@/components/projects/GenerationComparison'
import type {
  ComparisonRow,
  ComparisonSection,
  GenerationResults,
  GenerationSection,
} from '@/data/generationResults'

const even = { won: 0, lost: 0, outcome: 'indistinguishable' as const }

function makeRow(overrides: Partial<ComparisonRow> = {}): ComparisonRow {
  return {
    arm: 'onnx-dense',
    armLabel: 'Meaning only, shippable',
    eligibility: 'candidate',
    shipped: false,
    metrics: { factRecall: 0.8, faithfulness: 0.9, declineAccuracy: 0.97 },
    costPerAnswerUsd: 0.0002,
    vsShipped: { factRecall: even, faithfulness: even, declineAccuracy: even },
    ...overrides,
  }
}

/** A Comparison section, shaped exactly like the generated file. */
function makeComparison(overrides: Partial<ComparisonSection> = {}): ComparisonSection {
  return {
    generatedAt: '2026-10-12T00:00:00+00:00',
    commit: 'cmp4567',
    runUrl: 'https://example.test/run/9',
    split: 'holdout',
    shippedArm: 'bm25',
    generationModel: 'gpt-6-luna-2026-08-01',
    reasoningEffort: 'low',
    judge: 'jev-1.13.0',
    splitter: 'gpt-6-luna-2026-08-01',
    corpusChunks: 123,
    questions: 39,
    answerable: 33,
    outOfScope: 6,
    steps: { factRecall: 0.1, faithfulness: 0.05, declineAccuracy: 0.005 },
    arms: [
      makeRow({
        arm: 'bm25',
        armLabel: 'Keyword only',
        shipped: true,
        metrics: { factRecall: 0.7, faithfulness: 0.95, declineAccuracy: 1.0 },
        vsShipped: null,
      }),
      makeRow({
        vsShipped: {
          factRecall: { won: 9, lost: 1, outcome: 'ahead' },
          faithfulness: { won: 2, lost: 3, outcome: 'indistinguishable' },
          declineAccuracy: even,
        },
      }),
    ],
    ...overrides,
  }
}

/** The Shipped Arm section, from a different run with its own provenance. */
const shippedArm = {
  commit: 'main123',
  runUrl: 'https://example.test/run/1',
} as GenerationSection

function makeResults(comparison: ComparisonSection | null = makeComparison()): GenerationResults {
  return { schemaVersion: 1, shippedArm, comparison }
}

describe('GenerationComparison', () => {
  it('renders a row per Candidate Arm with its metrics at their rounding steps', () => {
    render(<GenerationComparison results={makeResults()} />)

    const row = within(screen.getByText('Meaning only, shippable').closest('tr')!)
    expect(row.getByText('0.8')).toBeInTheDocument()
    expect(row.getByText('0.90')).toBeInTheDocument()
    expect(row.getByText('0.970')).toBeInTheDocument()
  })

  it('marks the Shipped Arm, which every other row is compared with', () => {
    render(<GenerationComparison results={makeResults()} />)

    const row = within(screen.getByText('Keyword only').closest('tr')!)
    expect(row.getByText('IN PRODUCTION')).toBeInTheDocument()
  })

  it('shows each Arm’s questions won and lost against the Shipped Arm', () => {
    render(<GenerationComparison results={makeResults()} />)

    const row = within(screen.getByText('Meaning only, shippable').closest('tr')!)
    expect(row.getByText('9 won · 1 lost')).toBeInTheDocument()
    expect(row.getByText('2 won · 3 lost')).toBeInTheDocument()
  })

  it('names only differences beyond sampling noise', () => {
    render(<GenerationComparison results={makeResults()} />)

    const row = within(screen.getByText('Meaning only, shippable').closest('tr')!)
    expect(row.getByText('AHEAD')).toBeInTheDocument()
    expect(row.queryByText('BEHIND')).not.toBeInTheDocument()
    expect(row.queryByText(/indistinguishable/i)).not.toBeInTheDocument()
  })

  it('links to its own CI run, not the Shipped Arm section’s', () => {
    render(<GenerationComparison results={makeResults()} />)

    const link = screen.getByRole('link', { name: /commit cmp4567/ })
    expect(link).toHaveAttribute('href', 'https://example.test/run/9')
    expect(screen.queryByText(/main123/)).not.toBeInTheDocument()
  })

  it('reports the held-out sample and the model and Judge it measured', () => {
    render(<GenerationComparison results={makeResults()} />)

    expect(
      screen.getByText('39 held-out questions · 6 out of scope · 123 chunks')
    ).toBeInTheDocument()
    expect(screen.getByText('gpt-6-luna-2026-08-01')).toBeInTheDocument()
    expect(screen.getByText('jev-1.13.0')).toBeInTheDocument()
  })

  it('says so when no comparison has run yet, rather than rendering an empty table', () => {
    render(<GenerationComparison results={makeResults(null)} />)

    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText(/No comparison has been published yet/)).toBeInTheDocument()
  })

  it('renders the published document by default', () => {
    render(<GenerationComparison />)

    expect(screen.getByText('ARM COMPARISON')).toBeInTheDocument()
  })
})
