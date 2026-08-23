'use client'

import { useState, useEffect } from 'react'
import Button from '@/components/ui/Button'

const TAGLINE = 'Building intelligent systems at the intersection of AI and software engineering.'

const PROFILE_STATS = [
  { num: '5+', label: 'Years AI/ML' },
  { num: '8+', label: 'Years Defense' },
  { num: '4', label: 'Projects' },
]

const STACK = ['Python', 'TypeScript', 'FastAPI', 'Next.js', 'LLMs', 'RAG', 'AWS', 'Groq']

const HEADLINE_GRADIENT = {
  background:
    'linear-gradient(to bottom, #ffffff 0%, rgba(255,255,255,0.95) 40%, rgba(255,255,255,0.70) 100%)',
  WebkitBackgroundClip: 'text' as const,
  WebkitTextFillColor: 'transparent' as const,
  backgroundClip: 'text' as const,
}

export default function Hero() {
  const [typed, setTyped] = useState('')
  const [cardVisible, setCardVisible] = useState(false)

  useEffect(() => {
    if (typed.length >= TAGLINE.length) return
    const t = setTimeout(() => setTyped(TAGLINE.slice(0, typed.length + 1)), 30)
    return () => clearTimeout(t)
  }, [typed])

  useEffect(() => {
    const t = setTimeout(() => setCardVisible(true), 400)
    return () => clearTimeout(t)
  }, [])

  return (
    <section className="relative z-10 flex min-h-screen items-center overflow-hidden">
      <div className="relative mx-auto w-full max-w-7xl px-6 py-24 lg:py-32">
        <div className="grid items-center gap-12 lg:grid-cols-[3fr_2fr] lg:gap-16">
          {/* ── Left col ── */}
          <div className="space-y-8">
            {/* Status badge */}
            <div className="flex items-center gap-3">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#0ea5e9] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#0ea5e9]" />
              </span>
              <span className="font-mono text-[11px] tracking-widest text-[#8a8f98]">
                Available for opportunities
              </span>
            </div>

            {/* Headline */}
            <div>
              <h1
                className="text-5xl leading-none font-semibold tracking-[-0.03em] md:text-7xl lg:text-8xl"
                style={HEADLINE_GRADIENT}
              >
                David West
              </h1>
              <div className="mt-3 flex items-center gap-4">
                <span className="h-px w-12 bg-[#0ea5e9]/50" />
                <h2 className="font-mono text-lg tracking-widest text-[#0ea5e9] md:text-xl">
                  AI Engineer
                </h2>
              </div>
            </div>

            {/* Typewriter tagline */}
            <p className="min-h-[3.5rem] max-w-xl text-base leading-relaxed text-[#8a8f98] md:text-lg">
              <span className="sr-only">{TAGLINE}</span>
              <span aria-hidden="true">
                {typed}
                {typed.length < TAGLINE.length && (
                  <span className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 animate-[blink_1s_step-end_infinite] bg-[#0ea5e9] align-middle" />
                )}
              </span>
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="primary" size="lg" href="#projects">
                View My Work
              </Button>
              <Button variant="secondary" size="lg" href="#contact">
                Get in Touch
              </Button>
            </div>

            {/* Stats row */}
            <div className="flex gap-8 border-t border-white/[0.06] pt-6">
              {PROFILE_STATS.map(({ num, label }) => (
                <div key={label}>
                  <div className="text-2xl font-semibold tracking-tight" style={HEADLINE_GRADIENT}>
                    {num}
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] tracking-widest text-[#8a8f98]">
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right col — Profile card ── */}
          <div
            className="hidden lg:block"
            style={{
              opacity: cardVisible ? 1 : 0,
              transform: cardVisible ? 'translateX(0)' : 'translateX(20px)',
              transition:
                'opacity 700ms cubic-bezier(0.16, 1, 0.3, 1), transform 700ms cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div className="rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.08] to-white/[0.02] p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_8px_40px_rgba(0,0,0,0.4),0_0_80px_rgba(14,165,233,0.06)]">
              {/* Profile header */}
              <div className="mb-5 flex items-center gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.10] to-white/[0.04] text-sm font-semibold text-[#ededef]">
                  DW
                </div>
                <div>
                  <p className="text-sm font-medium text-[#ededef]">David West</p>
                  <p className="text-xs text-[#8a8f98]">AI Engineer</p>
                </div>
                <div className="ml-auto flex items-center gap-1.5 rounded-full border border-[#0ea5e9]/30 bg-[#0ea5e9]/10 px-3 py-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9]" />
                  <span className="font-mono text-[10px] tracking-widest text-[#0ea5e9]">Open</span>
                </div>
              </div>

              <div className="mb-5 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />

              {/* Info rows */}
              <div className="mb-5 space-y-3">
                {[
                  { label: 'Experience', value: '5+ yrs AI/ML · 8+ yrs defense' },
                  { label: 'Stack', value: 'Python · TypeScript · FastAPI' },
                  { label: 'Focus', value: 'LLMs · RAG · Production AI' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-baseline gap-3">
                    <span className="w-20 shrink-0 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                      {label}
                    </span>
                    <span className="text-sm text-[#ededef]/80">{value}</span>
                  </div>
                ))}
              </div>

              <div className="mb-4 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />

              {/* Capabilities */}
              <div>
                <p className="mb-3 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                  Capabilities
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {STACK.map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full border border-white/[0.08] px-2.5 py-0.5 font-mono text-[10px] tracking-widest text-[#8a8f98]"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <div className="flex flex-col items-center gap-2">
          <span className="font-mono text-[9px] tracking-[0.3em] text-[#8a8f98]/40">scroll</span>
          <div className="h-8 w-px bg-gradient-to-b from-[#8a8f98]/20 to-transparent" />
        </div>
      </div>
    </section>
  )
}
