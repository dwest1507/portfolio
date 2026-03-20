'use client'

import { useState, useEffect } from 'react'
import Button from '@/components/ui/Button'

const TAGLINE = 'Building intelligent systems at the intersection of AI and software engineering.'

const HUD_LINES = [
  { label: 'IDENTITY', value: 'David West' },
  { label: 'ROLE    ', value: 'AI Engineer' },
  { label: 'EXP     ', value: '5+ yrs AI/ML · 8+ yrs defense' },
  { label: 'STACK   ', value: 'Python · TypeScript · FastAPI' },
]

export default function Hero() {
  const [typed, setTyped] = useState('')
  const [hudVisible, setHudVisible] = useState(false)

  // One-shot typewriter for tagline
  useEffect(() => {
    if (typed.length >= TAGLINE.length) return
    const t = setTimeout(() => setTyped(TAGLINE.slice(0, typed.length + 1)), 35)
    return () => clearTimeout(t)
  }, [typed])

  // Slight delay before HUD appears
  useEffect(() => {
    const t = setTimeout(() => setHudVisible(true), 600)
    return () => clearTimeout(t)
  }, [])

  return (
    <section className="relative z-10 flex min-h-screen items-center overflow-hidden">
      {/* Gradient mesh — accent glows in corners */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 60% 50% at 20% 50%, rgba(0,255,136,0.06) 0%, transparent 70%), radial-gradient(ellipse 40% 40% at 80% 20%, rgba(0,212,255,0.04) 0%, transparent 60%), radial-gradient(ellipse 50% 60% at 70% 80%, rgba(255,0,255,0.03) 0%, transparent 60%)',
        }}
      />

      <div className="relative mx-auto w-full max-w-7xl px-6 py-24 lg:py-32">
        <div className="grid items-center gap-12 lg:grid-cols-[3fr_2fr] lg:gap-16">
          {/* ── Left col ── */}
          <div className="space-y-8">
            {/* Status badge */}
            <div className="flex items-center gap-3">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00ff88] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#00ff88]" />
              </span>
              <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#00ff88]">
                Available for opportunities
              </span>
            </div>

            {/* Name — glitch headline */}
            <div>
              <h1
                className="glitch-text glitch-animate font-[family-name:var(--font-heading)] text-5xl font-black uppercase leading-none tracking-widest text-[#e0e0e0] md:text-7xl lg:text-8xl"
                data-text="DAVID WEST"
              >
                DAVID WEST
              </h1>
              <div className="mt-3 flex items-center gap-4">
                <span className="h-px flex-1 max-w-[60px] bg-[#00ff88]" />
                <h2 className="neon-glow-accent font-[family-name:var(--font-heading)] text-xl font-bold uppercase tracking-[0.4em] text-[#00ff88] md:text-2xl">
                  AI Engineer
                </h2>
              </div>
            </div>

            {/* Typewriter tagline */}
            <p
              className="min-h-[3rem] max-w-xl font-[family-name:var(--font-body)] text-base leading-relaxed tracking-wide text-[#6b7280] md:text-lg"
              aria-label={TAGLINE}
            >
              {typed}
              {typed.length < TAGLINE.length && (
                <span className="inline-block w-0.5 animate-[blink_1s_step-end_infinite] bg-[#00ff88] align-middle">
                  &nbsp;
                </span>
              )}
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="glitch" size="lg" href="#projects">
                View My Work
              </Button>
              <Button variant="outline" size="lg" href="#contact">
                Get in Touch
              </Button>
            </div>

            {/* Stats row */}
            <div className="flex gap-8 border-t border-[#2a2a3a] pt-6">
              {[
                { num: '5+', label: 'Years AI/ML' },
                { num: '8+', label: 'Years Defense' },
                { num: '4', label: 'Projects' },
              ].map(({ num, label }) => (
                <div key={label}>
                  <div className="font-[family-name:var(--font-heading)] text-2xl font-bold text-[#00ff88]">
                    {num}
                  </div>
                  <div className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right col — HUD terminal (desktop only) ── */}
          <div
            className="hidden lg:block"
            style={{
              opacity: hudVisible ? 1 : 0,
              transform: hudVisible ? 'translateX(0)' : 'translateX(20px)',
              transition: 'opacity 800ms ease, transform 800ms ease',
            }}
          >
            <div className="clip-card relative border border-[#00ff88]/20 bg-[#0a0a0f]/80 shadow-[0_0_40px_rgba(0,255,136,0.08),inset_0_0_40px_rgba(0,255,136,0.02)]">
              {/* Corner accents */}
              <span className="pointer-events-none absolute left-0 top-0 h-5 w-5 border-l-2 border-t-2 border-[#00ff88]" />
              <span className="pointer-events-none absolute right-0 top-0 h-5 w-5 border-r-2 border-t-2 border-[#00ff88]" />
              <span className="pointer-events-none absolute bottom-0 left-0 h-5 w-5 border-b-2 border-l-2 border-[#00ff88]" />
              <span className="pointer-events-none absolute bottom-0 right-0 h-5 w-5 border-b-2 border-r-2 border-[#00ff88]" />

              {/* Terminal header */}
              <div className="flex items-center gap-2 border-b border-[#2a2a3a] px-4 py-2.5">
                <span className="h-2 w-2 rounded-full bg-[#ff3366] opacity-70" />
                <span className="h-2 w-2 rounded-full bg-[#ff9900] opacity-70" />
                <span className="h-2 w-2 rounded-full bg-[#00ff88] opacity-70" />
                <span className="ml-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                  profile_scan.exe
                </span>
              </div>

              <div className="space-y-5 p-6 font-[family-name:var(--font-body)] text-sm">
                {/* Scan output */}
                <div>
                  <p className="text-[#6b7280]">
                    <span className="text-[#00ff88]">$</span> ./scan --target david.west
                  </p>
                  <p className="mt-1 text-[#00ff88]">
                    [████████████████] 100% — LOADED
                  </p>
                </div>

                {/* Profile fields */}
                <div className="space-y-2 border-t border-[#2a2a3a] pt-4">
                  {HUD_LINES.map(({ label, value }) => (
                    <div key={label} className="flex gap-3">
                      <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.15em] text-[#6b7280]">
                        {label}
                      </span>
                      <span className="text-[#e0e0e0]">{'/'+'/'}</span>
                      <span className="text-[#00d4ff]">{value}</span>
                    </div>
                  ))}
                </div>

                {/* Capabilities */}
                <div className="border-t border-[#2a2a3a] pt-4">
                  <p className="mb-3 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280]">
                    {'// capabilities'}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {['LLMs', 'RAG', 'FAISS', 'FastAPI', 'Next.js', 'Groq', 'Modal', 'AWS'].map(
                      (skill) => (
                        <span
                          key={skill}
                          className="clip-card-sm border border-[#2a2a3a] px-2 py-0.5 font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.15em] text-[#6b7280]"
                        >
                          {skill}
                        </span>
                      )
                    )}
                  </div>
                </div>

                {/* Status */}
                <div className="border-t border-[#2a2a3a] pt-4">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00ff88] opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#00ff88]" />
                    </span>
                    <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#00ff88]">
                      Status: Open to Opportunities
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <div className="flex flex-col items-center gap-2">
          <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.3em] text-[#2a2a3a]">
            scroll
          </span>
          <div className="h-8 w-px bg-gradient-to-b from-[#2a2a3a] to-transparent" />
        </div>
      </div>
    </section>
  )
}
