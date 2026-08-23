import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FilterBar from '@/components/home/FilterBar'

const tags = ['All', 'Python', 'Next.js', 'Groq']

describe('FilterBar', () => {
  it('renders a button for every tag', () => {
    render(<FilterBar tags={tags} active="All" onChange={vi.fn()} />)
    for (const tag of tags) {
      expect(screen.getByRole('button', { name: tag })).toBeInTheDocument()
    }
  })

  it('marks only the active tag as pressed', () => {
    render(<FilterBar tags={tags} active="Python" onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Python' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onChange with the clicked tag', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<FilterBar tags={tags} active="All" onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'Groq' }))
    expect(onChange).toHaveBeenCalledWith('Groq')
  })

  it('calls onChange with "All" when All is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<FilterBar tags={tags} active="Python" onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'All' }))
    expect(onChange).toHaveBeenCalledWith('All')
  })
})
