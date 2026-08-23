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
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#050506]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-2">
        {/* Logo */}
        <Link
          href="/"
          className="inline-flex min-h-[44px] items-center text-lg font-semibold tracking-tight text-[#ededef] transition-colors duration-200 hover:text-white"
        >
          DW
          <span className="text-[#0ea5e9]">.</span>
        </Link>

        {/* Desktop nav */}
        <nav aria-label="Main navigation" className="hidden gap-8 md:flex">
          {navLinks.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="inline-flex min-h-[44px] items-center text-sm text-[#8a8f98] transition-colors duration-200 hover:text-[#ededef]"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:block">
          <a
            href="mailto:david.p.west2@gmail.com"
            className="rounded-lg bg-[#0ea5e9] px-4 py-2 text-sm font-medium text-[#082f49] shadow-[0_0_0_1px_rgba(14,165,233,0.5),0_4px_12px_rgba(14,165,233,0.25),inset_0_1px_0_0_rgba(255,255,255,0.15)] transition-all duration-200 hover:bg-[#38bdf8] hover:shadow-[0_0_0_1px_rgba(14,165,233,0.6),0_4px_20px_rgba(14,165,233,0.35),inset_0_1px_0_0_rgba(255,255,255,0.15)] active:scale-[0.98]"
          >
            Get in Touch
          </a>
        </div>

        {/* Mobile menu button */}
        <button
          className="flex min-h-[44px] min-w-[44px] items-center justify-center text-[#8a8f98] transition-colors hover:text-[#ededef] md:hidden"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-5 w-5"
            aria-hidden="true"
          >
            {menuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5"
              />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile nav */}
      {menuOpen && (
        <div
          className="border-t border-white/[0.06] bg-[#050506]/95 px-6 pb-6 backdrop-blur-xl md:hidden"
          style={{ animation: 'slide-down 0.2s cubic-bezier(0.16, 1, 0.3, 1)' }}
        >
          <nav aria-label="Mobile navigation">
            <ul className="flex flex-col gap-1 pt-4">
              {navLinks.map(({ href, label }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="block rounded-lg px-3 py-2.5 text-sm text-[#8a8f98] transition-colors hover:bg-white/[0.04] hover:text-[#ededef]"
                    onClick={() => setMenuOpen(false)}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
            <div className="mt-4 border-t border-white/[0.06] pt-4">
              <a
                href="mailto:david.p.west2@gmail.com"
                className="block rounded-lg bg-[#0ea5e9] px-4 py-3 text-center text-sm font-medium text-[#082f49] shadow-[0_0_0_1px_rgba(14,165,233,0.5),0_4px_12px_rgba(14,165,233,0.25)] transition-all duration-200 hover:bg-[#38bdf8]"
              >
                Get in Touch
              </a>
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}
