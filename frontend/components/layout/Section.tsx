import { type ReactNode } from 'react'

interface SectionProps {
  id?: string
  children: ReactNode
  className?: string
}

export default function Section({ id, children, className = '' }: SectionProps) {
  return (
    <section
      id={id}
      className={`relative z-10 py-24 lg:py-32 ${className}`}
    >
      <div className="mx-auto max-w-7xl px-6">{children}</div>
    </section>
  )
}
