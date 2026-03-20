import { notFound } from 'next/navigation'
import { readFile } from 'fs/promises'
import path from 'path'
import type { Metadata } from 'next'
import { compileMDX } from 'next-mdx-remote/rsc'
import { projects } from '@/data/projects'
import ProjectDetail from '@/components/projects/ProjectDetail'
import { mdxComponents } from '@/components/projects/mdxComponents'

export function generateStaticParams() {
  return projects.map((p) => ({ slug: p.slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  const project = projects.find((p) => p.slug === slug)
  if (!project) return {}
  return {
    title: `${project.title} — David West`,
    description: project.shortDescription,
    openGraph: {
      title: `${project.title} — David West`,
      description: project.shortDescription,
      type: 'website',
      images: ['/og-image.png'],
    },
    twitter: { card: 'summary_large_image' },
  }
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const project = projects.find((p) => p.slug === slug)
  if (!project) notFound()

  const mdxPath = path.join(process.cwd(), 'content', 'projects', `${slug}.mdx`)
  let source: string
  try {
    source = await readFile(mdxPath, 'utf-8')
  } catch {
    notFound()
  }

  const { content } = await compileMDX({
    source,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    components: mdxComponents as any,
    options: { parseFrontmatter: true },
  })

  return <ProjectDetail project={project} content={content} />
}
