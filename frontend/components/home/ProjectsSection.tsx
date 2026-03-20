'use client'

import { useState } from 'react'
import { projects, allTags } from '@/data/projects'
import FilterBar from '@/components/home/FilterBar'
import ProjectCard from '@/components/home/ProjectCard'
import FadeIn from '@/components/ui/FadeIn'

export default function ProjectsSection() {
  const [activeTag, setActiveTag] = useState('All')

  const filtered =
    activeTag === 'All' ? projects : projects.filter((p) => p.tags.includes(activeTag))

  return (
    <section id="projects" className="relative z-10 py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <FadeIn className="mb-12">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="mb-2 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.3em] text-[#00ff88]">
                {'// 02. projects'}
              </p>
              <h2 className="font-[family-name:var(--font-heading)] text-4xl font-bold uppercase tracking-wide text-[#e0e0e0] md:text-5xl">
                SELECTED_
                <br />
                <span className="text-[#00ff88]">WORK</span>
              </h2>
            </div>
            <div className="hidden text-right md:block">
              <p className="font-[family-name:var(--font-body)] text-sm text-[#6b7280]">
                {filtered.length} project{filtered.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </FadeIn>

        {/* Filter bar */}
        <FadeIn className="mb-10" delay={100}>
          <FilterBar tags={allTags} active={activeTag} onChange={setActiveTag} />
        </FadeIn>

        {/* Project grid */}
        <div className="grid gap-6 md:grid-cols-2">
          {filtered.map((project, i) => (
            <FadeIn key={project.slug} delay={i * 80}>
              <ProjectCard project={project} />
            </FadeIn>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="py-20 text-center">
            <p className="font-[family-name:var(--font-label)] text-sm uppercase tracking-[0.2em] text-[#6b7280]">
              &gt; no projects match filter: {activeTag}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
