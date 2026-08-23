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
    <section id="projects" className="relative z-10 border-t border-white/[0.06] py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <FadeIn className="mb-12">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="mb-2 font-mono text-[11px] tracking-widest text-[#0ea5e9]">Projects</p>
              <h2 className="text-4xl font-semibold tracking-tight text-[#ededef] md:text-5xl">
                Selected work
              </h2>
            </div>
            <div className="hidden text-right md:block">
              <p className="text-sm text-[#8a8f98]">
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
            <p className="text-sm text-[#8a8f98]">No projects match &ldquo;{activeTag}&rdquo;</p>
          </div>
        )}
      </div>
    </section>
  )
}
