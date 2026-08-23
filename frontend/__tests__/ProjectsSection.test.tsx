import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ProjectsSection from '@/components/home/ProjectsSection'
import { projects } from '@/data/projects'

vi.mock('next/image', () => ({
  default: (props: { src: string; alt: string; className?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={props.src} alt={props.alt} className={props.className} />
  ),
}))

describe('ProjectsSection', () => {
  it('shows all projects by default', () => {
    render(<ProjectsSection />)
    for (const project of projects) {
      expect(screen.getByRole('heading', { name: project.title })).toBeInTheDocument()
    }
    expect(screen.getByText(`${projects.length} projects`)).toBeInTheDocument()
  })

  it('filters cards down to projects matching the selected tag', async () => {
    const user = userEvent.setup()
    render(<ProjectsSection />)

    await user.click(screen.getByRole('button', { name: 'R' }))

    expect(screen.getByRole('heading', { name: 'Diamonds: Predicting Price' })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Generate Music with AI' })
    ).not.toBeInTheDocument()
    expect(screen.getByText('1 project')).toBeInTheDocument()
  })

  it('shows every project with the selected tag', async () => {
    const user = userEvent.setup()
    render(<ProjectsSection />)

    await user.click(screen.getByRole('button', { name: 'Streamlit' }))

    expect(screen.getByRole('heading', { name: 'Chat with Nietzsche' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Baby Name Popularity' })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Generate Music with AI' })
    ).not.toBeInTheDocument()
  })

  it('resets to all projects when All is clicked', async () => {
    const user = userEvent.setup()
    render(<ProjectsSection />)

    await user.click(screen.getByRole('button', { name: 'R' }))
    await user.click(screen.getByRole('button', { name: 'All' }))

    for (const project of projects) {
      expect(screen.getByRole('heading', { name: project.title })).toBeInTheDocument()
    }
  })
})
