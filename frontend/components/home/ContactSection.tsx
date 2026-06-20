import FadeIn from '@/components/ui/FadeIn'

export default function ContactSection() {
  return (
    <section id="contact" className="relative z-10 border-t border-white/[0.06] py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <FadeIn>
          <p className="mb-2 font-mono text-[11px] tracking-widest text-[#0ea5e9]">Contact</p>
          <h2 className="text-4xl font-semibold tracking-tight text-[#ededef] md:text-5xl">
            Let&apos;s connect
          </h2>
        </FadeIn>

        <FadeIn delay={150}>
          <div className="relative mt-12 overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.08] to-white/[0.02] p-8 shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_2px_20px_rgba(0,0,0,0.4)] md:p-12">
            {/* Top accent line */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#0ea5e9]/30 to-transparent" />

            <div className="max-w-2xl space-y-6">
              <p className="text-base leading-relaxed text-[#8a8f98]">
                I&apos;m open to AI engineering roles, applied ML work, and interesting side
                projects. Whether you&apos;re building something ambitious or just want to talk
                shop, reach out.
              </p>

              <div className="space-y-4 border-t border-white/[0.06] pt-6">
                <div className="flex items-center gap-5">
                  <span className="w-16 shrink-0 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                    Email
                  </span>
                  <a
                    href="mailto:david.p.west2@gmail.com"
                    className="text-sm text-[#ededef] transition-colors duration-150 hover:text-[#0ea5e9]"
                  >
                    david.p.west2@gmail.com
                  </a>
                </div>
                <div className="flex items-center gap-5">
                  <span className="w-16 shrink-0 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                    LinkedIn
                  </span>
                  <a
                    href="https://www.linkedin.com/in/david-west-277509b1/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
                  >
                    linkedin.com/in/david-west-277509b1 ↗
                  </a>
                </div>
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  )
}
