import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import Header from '@/components/layout/Header'

describe('Header', () => {
  it('renders the desktop navigation links', () => {
    render(<Header />)
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(nav).toBeInTheDocument()
    for (const label of ['Projects', 'About', 'Contact']) {
      expect(screen.getByRole('link', { name: label })).toHaveAttribute(
        'href',
        `/#${label.toLowerCase()}`
      )
    }
  })

  it('renders the email CTA', () => {
    render(<Header />)
    expect(screen.getByRole('link', { name: 'Get in Touch' })).toHaveAttribute(
      'href',
      'mailto:david.p.west2@gmail.com'
    )
  })

  it('opens and closes the mobile menu', async () => {
    const user = userEvent.setup()
    render(<Header />)

    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' })).not.toBeInTheDocument()

    const menuButton = screen.getByRole('button', { name: 'Open menu' })
    await user.click(menuButton)
    expect(screen.getByRole('navigation', { name: 'Mobile navigation' })).toBeInTheDocument()
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button', { name: 'Close menu' }))
    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' })).not.toBeInTheDocument()
  })

  it('closes the mobile menu when a nav link is clicked', async () => {
    const user = userEvent.setup()
    render(<Header />)

    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    const mobileNav = screen.getByRole('navigation', { name: 'Mobile navigation' })
    const { getByRole } = within(mobileNav)
    await user.click(getByRole('link', { name: 'Projects' }))

    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' })).not.toBeInTheDocument()
  })
})
