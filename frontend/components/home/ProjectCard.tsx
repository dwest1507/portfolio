import Image from 'next/image'
import Link from 'next/link'
import Tag from '@/components/ui/Tag'
import { type Project } from '@/data/projects'

interface ProjectCardProps {
  project: Project
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const isExternalLive = project.liveUrl.startsWith('http')

  return (
    <article className="clip-card group relative flex flex-col border border-[#2a2a3a] bg-[#12121a] transition-all duration-300 hover:-translate-y-1 hover:border-[#00ff88]/60 hover:shadow-[0_0_20px_rgba(0,255,136,0.12),0_8px_32px_rgba(0,0,0,0.4)]">
      {/* Thumbnail */}
      <div className="relative h-44 w-full overflow-hidden border-b border-[#2a2a3a] bg-[#0a0a0f]">
        {project.thumbnail ? (
          <Image
            src={project.thumbnail}
            alt={project.title}
            fill
            className="object-cover opacity-80 transition-all duration-500 group-hover:opacity-100 group-hover:scale-[1.02]"
            sizes="(max-width: 768px) 100vw, 50vw"
          />
        ) : (
          /* Placeholder grid pattern when no image */
          <div
            aria-hidden
            className="absolute inset-0 flex items-center justify-center"
            style={{
              backgroundImage:
                'linear-gradient(rgba(0,255,136,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,136,0.04) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          >
            <span className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#2a2a3a]">
              {project.slug}
            </span>
          </div>
        )}
        {/* Year badge */}
        <div className="absolute right-3 top-3 clip-card-sm border border-[#2a2a3a] bg-[#0a0a0f]/80 px-2 py-0.5">
          <span className="font-[family-name:var(--font-label)] text-[9px] uppercase tracking-[0.2em] text-[#6b7280]">
            {project.year}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col p-5 gap-4">
        <div>
          <h3 className="font-[family-name:var(--font-heading)] text-base font-bold uppercase tracking-wide text-[#e0e0e0] group-hover:text-[#00ff88] transition-colors duration-200">
            {project.title}
          </h3>
          <p className="mt-2 font-[family-name:var(--font-body)] text-sm leading-relaxed text-[#6b7280]">
            {project.shortDescription}
          </p>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5">
          {project.tags.map((tag) => (
            <Tag key={tag} variant="muted">
              {tag}
            </Tag>
          ))}
        </div>

        {/* Links */}
        <div className="mt-auto flex items-center gap-3 border-t border-[#2a2a3a] pt-4">
          <Link
            href={`/projects/${project.slug}`}
            className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#00ff88] transition-all duration-150 hover:neon-glow-accent"
          >
            Case Study →
          </Link>
          <span className="text-[#2a2a3a]">|</span>
          <a
            href={project.liveUrl}
            target={isExternalLive ? '_blank' : '_self'}
            rel={isExternalLive ? 'noopener noreferrer' : undefined}
            className="font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#00d4ff] transition-all duration-150 hover:text-[#00ff88]"
          >
            Live App ↗
          </a>
          <a
            href={project.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] text-[#6b7280] transition-colors duration-150 hover:text-[#e0e0e0]"
          >
            GitHub
          </a>
        </div>
      </div>
    </article>
  )
}
