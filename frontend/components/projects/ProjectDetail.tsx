import type { ReactNode } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { type Project } from '@/data/projects'
import Button from '@/components/ui/Button'
import Tag from '@/components/ui/Tag'
import FadeIn from '@/components/ui/FadeIn'

interface ProjectDetailProps {
  project: Project
  content: ReactNode
}

// ─── System info row ─────────────────────────────────────────────────────────

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.2em] text-[#6b7280]">
        {label}
      </span>
      <span
        className={`font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.15em] ${accent ? 'text-[#00ff88]' : 'text-[#e0e0e0]'}`}
      >
        {value}
      </span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ProjectDetail({ project, content }: ProjectDetailProps) {
  const isExternalLive = project.liveUrl.startsWith('http')
  const liveLabel = project.liveUrl.endsWith('.html') ? 'View Analysis ↗' : 'Live App ↗'

  return (
    <main className="relative z-10 min-h-screen">
      {/* ── Breadcrumb nav ─────────────────────────────────────────────── */}
      <div className="sticky top-16 z-40 border-b border-[#2a2a3a] bg-[#0a0a0f]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
          <Link
            href="/#projects"
            className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] transition-colors duration-150 hover:text-[#00ff88]"
          >
            ← Projects
          </Link>
          <span aria-hidden className="text-[#2a2a3a]">
            /
          </span>
          <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#e0e0e0]">
            {project.slug}
          </span>
        </div>
      </div>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-[#2a2a3a] py-20 lg:py-28">
        {/* Background: radial gradient mesh */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse 70% 50% at 65% 60%, rgba(0,255,136,0.04) 0%, transparent 65%), radial-gradient(ellipse 40% 60% at 10% 80%, rgba(0,212,255,0.025) 0%, transparent 55%)',
          }}
        />
        {/* Subtle horizontal scan accent */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              'repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,255,136,0.04) 40px)',
          }}
        />

        <div className="relative mx-auto max-w-7xl px-6">
          {/* Mobile thumbnail — shown only below lg */}
          {project.thumbnail && (
            <div className="relative mb-10 h-52 w-full overflow-hidden clip-card border border-[#2a2a3a] lg:hidden">
              <Image
                src={project.thumbnail}
                alt={project.title}
                fill
                className="object-cover opacity-90"
                sizes="100vw"
                priority
              />
              <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-[#0a0a0f]/60 to-transparent" />
            </div>
          )}

          <div className="grid grid-cols-1 gap-12 lg:grid-cols-5">
            {/* Left: title + meta */}
            <div className="lg:col-span-3">
              <FadeIn>
                {/* Meta bar */}
                <div className="mb-6 flex items-center gap-3">
                  <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.3em] text-[#6b7280]">
                    {project.year}
                  </span>
                  <span aria-hidden className="text-[#2a2a3a]">
                    —
                  </span>
                  <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.3em] text-[#00ff88]">
                    Case Study
                  </span>
                  {project.featured && (
                    <>
                      <span aria-hidden className="text-[#2a2a3a]">
                        —
                      </span>
                      <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.3em] text-[#ff00ff]">
                        Featured
                      </span>
                    </>
                  )}
                </div>

                {/* Glitch title */}
                <h1
                  className="glitch-text glitch-animate font-[family-name:var(--font-heading)] text-4xl font-black uppercase leading-tight tracking-wide text-[#e0e0e0] sm:text-5xl lg:text-6xl"
                  data-text={project.title}
                >
                  {project.title}
                </h1>

                {/* Description */}
                <p className="mt-6 max-w-xl font-[family-name:var(--font-body)] text-sm leading-7 text-[#6b7280] lg:text-base lg:leading-8">
                  {project.shortDescription}
                </p>

                {/* Tags */}
                <div className="mt-6 flex flex-wrap gap-2">
                  {project.tags.map((tag) => (
                    <Tag key={tag} variant="muted">
                      {tag}
                    </Tag>
                  ))}
                </div>

                {/* CTA buttons */}
                <div className="mt-8 flex flex-wrap gap-3">
                  <Button
                    href={project.liveUrl}
                    target={isExternalLive ? '_blank' : '_self'}
                    rel={isExternalLive ? 'noopener noreferrer' : undefined}
                    variant="glitch"
                    size="lg"
                  >
                    {liveLabel}
                  </Button>
                  <Button
                    href={project.repoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="outline"
                    size="lg"
                  >
                    GitHub →
                  </Button>
                </div>
              </FadeIn>
            </div>

            {/* Right: thumbnail + system info terminal card (desktop) */}
            <div className="hidden lg:col-span-2 lg:flex lg:flex-col lg:gap-4 lg:items-start lg:pt-14">
              {project.thumbnail && (
                <FadeIn delay={80} className="w-full">
                  <div className="relative h-44 w-full overflow-hidden clip-card border border-[#2a2a3a] shadow-[0_0_20px_rgba(0,255,136,0.08)]">
                    <Image
                      src={project.thumbnail}
                      alt={project.title}
                      fill
                      className="object-cover opacity-90"
                      sizes="40vw"
                      priority
                    />
                    <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-[#0a0a0f]/40 to-transparent" />
                  </div>
                </FadeIn>
              )}
              <FadeIn delay={120} className="w-full">
                <div className="clip-card border border-[#2a2a3a] bg-[#12121a]">
                  {/* Terminal header */}
                  <div className="flex items-center gap-1.5 border-b border-[#2a2a3a] bg-[#1c1c2e] px-4 py-3">
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ff3366]" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ff8800]" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#00ff88]" />
                    <span className="ml-3 font-[family-name:var(--font-label)] text-[8px] uppercase tracking-[0.25em] text-[#6b7280]">
                      SYSTEM_INFO.cfg
                    </span>
                  </div>

                  {/* Info rows */}
                  <div className="space-y-3 p-5">
                    <InfoRow label="PROJECT" value={project.slug.toUpperCase()} />
                    <InfoRow label="YEAR" value={project.year.toString()} />
                    <InfoRow
                      label="TECH_STACK"
                      value={`${project.tags.length} TECHNOLOGIES`}
                    />
                    <InfoRow
                      label="STATUS"
                      value={isExternalLive ? 'LIVE' : 'STATIC'}
                      accent={isExternalLive}
                    />
                  </div>

                  {/* Tech stack tags */}
                  <div className="border-t border-[#2a2a3a] p-5">
                    <p className="mb-3 font-[family-name:var(--font-label)] text-[8px] uppercase tracking-[0.25em] text-[#6b7280]">
                      TECHNOLOGIES
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      {project.tags.map((tag) => (
                        <span
                          key={tag}
                          className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.15em] text-[#00ff88]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </FadeIn>
            </div>
          </div>
        </div>
      </section>

      {/* ── MDX content ────────────────────────────────────────────────── */}
      <FadeIn delay={80}>
        <article className="mx-auto max-w-3xl px-6 py-20 lg:py-28">
          {content}
        </article>
      </FadeIn>

      {/* ── Bottom nav ─────────────────────────────────────────────────── */}
      <div className="border-t border-[#2a2a3a]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-10">
          <Link
            href="/#projects"
            className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] transition-colors duration-150 hover:text-[#00ff88]"
          >
            ← All Projects
          </Link>
          <Link
            href="/#contact"
            className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] transition-colors duration-150 hover:text-[#00ff88]"
          >
            Contact →
          </Link>
        </div>
      </div>
    </main>
  )
}
