import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="relative z-10 mt-auto border-t border-[#2a2a3a] bg-[#0a0a0f]">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
        <p
          className="text-xs tracking-widest text-[#6b7280]"
          style={{ fontFamily: 'var(--font-label)' }}
        >
          © {new Date().getFullYear()} David West
        </p>

        <nav aria-label="Footer navigation" className="flex gap-6">
          <Link
            href="mailto:dwest1507@gmail.com"
            className="text-xs tracking-widest text-[#6b7280] transition-colors duration-150 hover:text-[#00ff88]"
            style={{ fontFamily: 'var(--font-label)' }}
          >
            Email
          </Link>
          <Link
            href="https://www.linkedin.com/in/david-west-277509b1/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs tracking-widest text-[#6b7280] transition-colors duration-150 hover:text-[#00ff88]"
            style={{ fontFamily: 'var(--font-label)' }}
          >
            LinkedIn
          </Link>
        </nav>
      </div>
    </footer>
  )
}
