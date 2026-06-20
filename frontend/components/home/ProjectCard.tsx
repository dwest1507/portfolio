'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useRef, useState } from 'react'
import Tag from '@/components/ui/Tag'
import { type Project } from '@/data/projects'

interface ProjectCardProps {
  project: Project
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const isExternalLive = project.liveUrl.startsWith('http')
  const cardRef = useRef<HTMLDivElement>(null)
  const [spotPos, setSpotPos] = useState({ x: 0, y: 0 })
  const [spotVisible, setSpotVisible] = useState(false)

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    setSpotPos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  return (
    <article
      ref={cardRef}
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.08] to-white/[0.02] shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_2px_20px_rgba(0,0,0,0.4)] transition-all duration-300 hover:border-white/[0.10] hover:shadow-[0_0_0_1px_rgba(255,255,255,0.10),0_8px_40px_rgba(0,0,0,0.5),0_0_80px_rgba(14,165,233,0.08)]"
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setSpotVisible(true)}
      onMouseLeave={() => setSpotVisible(false)}
    >
      {/* Mouse spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 transition-opacity duration-300"
        style={{
          opacity: spotVisible ? 1 : 0,
          background: `radial-gradient(300px circle at ${spotPos.x}px ${spotPos.y}px, rgba(14,165,233,0.10), transparent)`,
        }}
      />

      {/* Stretched overlay link */}
      <Link
        href={`/projects/${project.slug}`}
        className="absolute inset-0 z-0"
        aria-label={project.title}
      />

      {/* Thumbnail */}
      <div className="relative h-44 w-full overflow-hidden border-b border-white/[0.06] bg-[#0a0a0c]">
        {project.thumbnail ? (
          <Image
            src={project.thumbnail}
            alt={project.title}
            fill
            className="object-cover opacity-70 transition-all duration-500 group-hover:scale-[1.02] group-hover:opacity-90"
            sizes="(max-width: 768px) 100vw, 50vw"
          />
        ) : (
          <div
            aria-hidden
            className="absolute inset-0 flex items-center justify-center"
            style={{
              backgroundImage:
                'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
              backgroundSize: '32px 32px',
            }}
          >
            <span className="font-mono text-[10px] tracking-[0.3em] text-[#8a8f98]/30">
              {project.slug}
            </span>
          </div>
        )}
        {/* Year badge */}
        <div className="absolute right-3 top-3 rounded-full border border-white/[0.08] bg-[#050506]/80 px-2.5 py-0.5 backdrop-blur-sm">
          <span className="font-mono text-[9px] tracking-widest text-[#8a8f98]">
            {project.year}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div>
          <h3 className="font-medium text-[#ededef] transition-colors duration-200 group-hover:text-white">
            {project.title}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-[#8a8f98]">{project.shortDescription}</p>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5">
          {project.tags.map((tag) => (
            <Tag key={tag} variant="muted">
              {tag}
            </Tag>
          ))}
        </div>

        {/* Links — z-10 to sit above stretched overlay */}
        <div className="relative z-10 mt-auto flex items-center gap-3 border-t border-white/[0.06] pt-4">
          <a
            href={project.liveUrl}
            target={isExternalLive ? '_blank' : '_self'}
            rel={isExternalLive ? 'noopener noreferrer' : undefined}
            className="font-mono text-[10px] tracking-widest text-[#0ea5e9] transition-colors duration-150 hover:text-[#38bdf8]"
          >
            Live App ↗
          </a>
          <a
            href={project.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors duration-150 hover:text-[#ededef]"
          >
            GitHub
          </a>
        </div>
      </div>
    </article>
  )
}
