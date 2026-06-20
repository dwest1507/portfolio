import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="relative z-10 mt-auto border-t border-white/[0.06] bg-[#020203]">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
        <p className="text-xs text-[#8a8f98]">© {new Date().getFullYear()} David West</p>

        <nav aria-label="Footer navigation" className="flex gap-6">
          <Link
            href="mailto:david.p.west2@gmail.com"
            className="text-xs text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            Email
          </Link>
          <Link
            href="https://www.linkedin.com/in/david-west-277509b1/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            LinkedIn
          </Link>
        </nav>
      </div>
    </footer>
  )
}
