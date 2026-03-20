'use client'

import Link from 'next/link'
import { useState } from 'react'

const navLinks = [
  { href: '/#projects', label: 'Projects' },
  { href: '/#about', label: 'About' },
  { href: '/#contact', label: 'Contact' },
]

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 border-b border-[#2a2a3a] bg-[#0a0a0f]/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Logo / Name */}
        <Link
          href="/"
          className="font-heading text-lg font-bold tracking-widest text-[#00ff88] transition-all duration-150 hover:text-shadow-[0_0_12px_#00ff88]"
          style={{ fontFamily: 'var(--font-heading)' }}
        >
          DW<span className="text-[#e0e0e0]">.</span>
        </Link>

        {/* Desktop nav */}
        <nav aria-label="Main navigation" className="hidden gap-8 md:flex">
          {navLinks.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="font-label text-sm tracking-widest text-[#6b7280] transition-all duration-150 hover:text-[#00ff88]"
              style={{ fontFamily: 'var(--font-label)' }}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Mobile menu button */}
        <button
          className="flex min-h-[44px] min-w-[44px] items-center justify-center text-[#6b7280] hover:text-[#00ff88] md:hidden"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <span className="font-label text-lg">{menuOpen ? '×' : '≡'}</span>
        </button>
      </div>

      {/* Mobile nav */}
      {menuOpen && (
        <nav
          aria-label="Mobile navigation"
          className="border-t border-[#2a2a3a] bg-[#0a0a0f] px-6 pb-4 md:hidden"
        >
          <ul className="flex flex-col gap-4 pt-4">
            {navLinks.map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="font-label block py-2 text-sm tracking-widest text-[#6b7280] hover:text-[#00ff88]"
                  style={{ fontFamily: 'var(--font-label)' }}
                  onClick={() => setMenuOpen(false)}
                >
                  <span className="text-[#00ff88]">&gt; </span>
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </header>
  )
}
