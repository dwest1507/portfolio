import { describe, expect, it } from 'vitest'
import fs from 'fs'
import path from 'path'
import { projects, allTags } from '@/data/projects'

describe('projects data', () => {
  it('has a slug-matched MDX write-up for every project', () => {
    for (const project of projects) {
      const mdx = path.join(process.cwd(), 'content', 'projects', `${project.slug}.mdx`)
      expect(fs.existsSync(mdx), `missing content/projects/${project.slug}.mdx`).toBe(true)
    }
  })

  it('has unique slugs', () => {
    const slugs = projects.map((p) => p.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
  })

  it('includes the portfolio itself as a project', () => {
    const self = projects.find((p) => p.slug === 'portfolio')
    expect(self).toBeDefined()
    expect(self!.tags).toContain('Evals')
  })

  it('exposes every project tag through allTags, led by All', () => {
    expect(allTags[0]).toBe('All')
    for (const project of projects) {
      for (const tag of project.tags) {
        expect(allTags).toContain(tag)
      }
    }
  })
})
