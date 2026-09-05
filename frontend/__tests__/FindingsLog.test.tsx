import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FindingsLog from '@/components/projects/FindingsLog'
import { findings } from '@/data/evalFindings'

describe('FindingsLog', () => {
  it('renders every finding with what was seen and what changed', () => {
    render(<FindingsLog />)
    for (const finding of findings) {
      const entry = screen.getByText(finding.title).closest('li')!
      expect(within(entry).getByText(finding.observed)).toBeInTheDocument()
      expect(within(entry).getByText(/What changed:/)).toBeInTheDocument()
    }
  })

  it('gives each entry a machine-readable date', () => {
    render(<FindingsLog />)
    for (const finding of findings) {
      const entry = screen.getByText(finding.title).closest('li')!
      expect(within(entry).getByRole('time')).toHaveAttribute('datetime', finding.date)
    }
  })

  it('shows the metric movement when a finding records one', () => {
    render(<FindingsLog />)
    for (const finding of findings) {
      if (!finding.move) continue
      const entry = screen.getByText(finding.title).closest('li')!
      expect(within(entry).getByText(finding.move.before.toFixed(3))).toBeInTheDocument()
      expect(within(entry).getByText(finding.move.after.toFixed(3))).toBeInTheDocument()
      expect(within(entry).getByText(finding.move.metric)).toBeInTheDocument()
    }
  })

  it('lists findings newest first', () => {
    const dates = findings.map((f) => f.date)
    expect([...dates].sort().reverse()).toEqual(dates)
  })

  it('gives every finding a unique id', () => {
    expect(new Set(findings.map((f) => f.id)).size).toBe(findings.length)
  })
})
