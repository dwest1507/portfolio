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

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="font-mono text-[10px] tracking-widest text-[#8a8f98]/60">{label}</span>
      <span
        className={`font-mono text-[10px] tracking-widest ${accent ? 'text-[#0ea5e9]' : 'text-[#ededef]'}`}
      >
        {value}
      </span>
    </div>
  )
}

export default function ProjectDetail({ project, content }: ProjectDetailProps) {
  const isExternalLive = project.liveUrl.startsWith('http')
  const liveLabel =
    project.liveLabel ?? (project.liveUrl.endsWith('.html') ? 'View Analysis ↗' : 'Live App ↗')

  return (
    <main className="relative z-10 min-h-screen">
      {/* Breadcrumb nav */}
      <div className="sticky top-16 z-40 border-b border-white/[0.06] bg-[#050506]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
          <Link
            href="/#projects"
            className="font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            ← Projects
          </Link>
          <span aria-hidden className="text-[#8a8f98]/30">
            /
          </span>
          <span className="font-mono text-[10px] tracking-widest text-[#ededef]">
            {project.slug}
          </span>
        </div>
      </div>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/[0.06] py-20 lg:py-28">
        <div className="relative mx-auto max-w-7xl px-6">
          {/* Mobile thumbnail */}
          {project.thumbnail && (
            <div className="relative mb-10 h-52 w-full overflow-hidden rounded-2xl border border-white/[0.06] lg:hidden">
              <Image
                src={project.thumbnail}
                alt={project.title}
                fill
                className="object-cover opacity-80"
                sizes="100vw"
                priority
              />
              <div
                aria-hidden
                className="absolute inset-0 bg-gradient-to-t from-[#050506]/60 to-transparent"
              />
            </div>
          )}

          <div className="grid grid-cols-1 gap-12 lg:grid-cols-5">
            {/* Left: title + meta */}
            <div className="lg:col-span-3">
              <FadeIn>
                {/* Meta bar */}
                <div className="mb-6 flex items-center gap-3">
                  <span className="font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                    {project.year}
                  </span>
                  <span aria-hidden className="text-[#8a8f98]/20">
                    —
                  </span>
                  <span className="font-mono text-[10px] tracking-widest text-[#0ea5e9]">
                    Case Study
                  </span>
                  {project.featured && (
                    <>
                      <span aria-hidden className="text-[#8a8f98]/20">
                        —
                      </span>
                      <span className="font-mono text-[10px] tracking-widest text-[#8a8f98]">
                        Featured
                      </span>
                    </>
                  )}
                </div>

                {/* Title */}
                <h1
                  className="text-4xl leading-tight font-semibold tracking-tight text-[#ededef] sm:text-5xl lg:text-6xl"
                  style={{
                    background:
                      'linear-gradient(to bottom, #ffffff 0%, rgba(255,255,255,0.80) 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  {project.title}
                </h1>

                {/* Description */}
                <p className="mt-6 max-w-xl text-sm leading-7 text-[#8a8f98] lg:text-base lg:leading-8">
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
                    variant="primary"
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

            {/* Right: thumbnail + info card (desktop) */}
            <div className="hidden lg:col-span-2 lg:flex lg:flex-col lg:items-start lg:gap-4 lg:pt-14">
              {project.thumbnail && (
                <FadeIn delay={80} className="w-full">
                  <div className="relative h-44 w-full overflow-hidden rounded-2xl border border-white/[0.06] shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_8px_32px_rgba(0,0,0,0.4)]">
                    <Image
                      src={project.thumbnail}
                      alt={project.title}
                      fill
                      className="object-cover opacity-80"
                      sizes="40vw"
                      priority
                    />
                    <div
                      aria-hidden
                      className="absolute inset-0 bg-gradient-to-t from-[#050506]/40 to-transparent"
                    />
                  </div>
                </FadeIn>
              )}

              <FadeIn delay={120} className="w-full">
                <div className="rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.08] to-white/[0.02] shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_2px_20px_rgba(0,0,0,0.4)]">
                  <div className="space-y-3 p-5">
                    <InfoRow label="Project" value={project.slug.toUpperCase()} />
                    <InfoRow label="Year" value={project.year.toString()} />
                    <InfoRow label="Tech stack" value={`${project.tags.length} technologies`} />
                    <InfoRow
                      label="Status"
                      value={isExternalLive ? 'Live' : 'Static'}
                      accent={isExternalLive}
                    />
                  </div>

                  <div className="border-t border-white/[0.06] p-5">
                    <p className="mb-3 font-mono text-[10px] tracking-widest text-[#8a8f98]/60">
                      Technologies
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      {project.tags.map((tag) => (
                        <span
                          key={tag}
                          className="font-mono text-[10px] tracking-widest text-[#0ea5e9]"
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

      {/* MDX content */}
      <FadeIn delay={80}>
        <article className="mx-auto max-w-3xl px-6 py-20 lg:py-28">{content}</article>
      </FadeIn>

      {/* Bottom nav */}
      <div className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-10">
          <Link
            href="/#projects"
            className="font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            ← All Projects
          </Link>
          <Link
            href="/#contact"
            className="font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            Contact →
          </Link>
        </div>
      </div>
    </main>
  )
}
