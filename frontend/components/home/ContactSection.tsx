import FadeIn from '@/components/ui/FadeIn'

export default function ContactSection() {
  return (
    <section id="contact" className="relative z-10 py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <FadeIn>
          <p className="mb-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#00ff88]">
            {'// 04. contact'}
          </p>
          <h2 className="font-[family-name:var(--font-heading)] text-4xl font-bold uppercase tracking-wide text-[#e0e0e0] md:text-5xl">
            LET&apos;S
            <br />
            <span className="text-[#00ff88]">CONNECT_</span>
          </h2>
        </FadeIn>

        <FadeIn delay={150}>
          <div className="mt-12 clip-card relative border border-[#2a2a3a] bg-[#0a0a0f]">
            {/* Corner accents */}
            <span className="pointer-events-none absolute left-0 top-0 h-5 w-5 border-l-2 border-t-2 border-[#00ff88]/40" />
            <span className="pointer-events-none absolute right-0 top-0 h-5 w-5 border-r-2 border-t-2 border-[#00ff88]/40" />
            <span className="pointer-events-none absolute bottom-0 left-0 h-5 w-5 border-b-2 border-l-2 border-[#00ff88]/40" />
            <span className="pointer-events-none absolute bottom-0 right-0 h-5 w-5 border-b-2 border-r-2 border-[#00ff88]/40" />

            <div className="p-8 md:p-12">
              <div className="max-w-2xl space-y-6 font-[family-name:var(--font-body)] text-sm">
                <p className="text-[#e0e0e0]/80 leading-relaxed">
                  <span className="text-[#00ff88]">&gt;</span>{' '}
                  I&apos;m open to AI engineering roles, applied ML work, and interesting side projects.
                  Whether you&apos;re building something ambitious or just want to talk shop, reach out.
                </p>

                <div className="space-y-3 border-t border-[#2a2a3a] pt-6">
                  <div className="flex items-center gap-4">
                    <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] w-16">
                      Email
                    </span>
                    <a
                      href="mailto:david.p.west2@gmail.com"
                      className="text-[#00ff88] transition-all duration-150 hover:neon-glow-accent"
                    >
                      david.p.west2@gmail.com
                    </a>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] w-16">
                      LinkedIn
                    </span>
                    <a
                      href="https://www.linkedin.com/in/david-west-277509b1/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#00d4ff] transition-colors duration-150 hover:text-[#00ff88]"
                    >
                      linkedin.com/in/david-west-277509b1 ↗
                    </a>
                  </div>
                </div>

                <div className="pt-2">
                  <p className="cursor-blink font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                    &gt; awaiting transmission
                  </p>
                </div>
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  )
}
