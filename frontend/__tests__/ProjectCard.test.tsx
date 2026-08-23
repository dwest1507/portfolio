import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ProjectCard from '@/components/home/ProjectCard'
import type { Project } from '@/data/projects'

vi.mock('next/image', () => ({
  default: (props: { src: string; alt: string; className?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={props.src} alt={props.alt} className={props.className} />
  ),
}))

const externalProject: Project = {
  slug: 'test-project',
  title: 'Test Project',
  shortDescription: 'A project used for testing the card.',
  thumbnail: '/projects/test.png',
  tags: ['Python', 'FastAPI'],
  liveUrl: 'https://example.com/live',
  repoUrl: 'https://github.com/dwest1507/test-project',
  featured: false,
  year: 2025,
}

const internalProject: Project = {
  ...externalProject,
  slug: 'internal-project',
  title: 'Internal Project',
  liveUrl: '/projects/some-static-page.html',
}

describe('ProjectCard', () => {
  it('renders title, description, tags, and year', () => {
    render(<ProjectCard project={externalProject} />)
    expect(screen.getByRole('heading', { name: 'Test Project' })).toBeInTheDocument()
    expect(screen.getByText('A project used for testing the card.')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('FastAPI')).toBeInTheDocument()
    expect(screen.getByText('2025')).toBeInTheDocument()
  })

  it('links to the detail page via the stretched overlay link', () => {
    render(<ProjectCard project={externalProject} />)
    expect(screen.getByRole('link', { name: 'Test Project' })).toHaveAttribute(
      'href',
      '/projects/test-project'
    )
  })

  it('opens an external live URL in a new tab with rel protection', () => {
    render(<ProjectCard project={externalProject} />)
    const liveLink = screen.getByRole('link', { name: /live app/i })
    expect(liveLink).toHaveAttribute('href', 'https://example.com/live')
    expect(liveLink).toHaveAttribute('target', '_blank')
    expect(liveLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('opens an internal live URL in the same tab', () => {
    render(<ProjectCard project={internalProject} />)
    const liveLink = screen.getByRole('link', { name: /live app/i })
    expect(liveLink).toHaveAttribute('href', '/projects/some-static-page.html')
    expect(liveLink).toHaveAttribute('target', '_self')
    expect(liveLink).not.toHaveAttribute('rel')
  })

  it('links to the GitHub repo in a new tab', () => {
    render(<ProjectCard project={externalProject} />)
    const repoLink = screen.getByRole('link', { name: 'GitHub' })
    expect(repoLink).toHaveAttribute('href', 'https://github.com/dwest1507/test-project')
    expect(repoLink).toHaveAttribute('target', '_blank')
  })
})
