import { type ReactNode } from 'react'

interface TagProps {
  children: ReactNode
  variant?: 'accent' | 'secondary' | 'tertiary' | 'muted'
  className?: string
}

export default function Tag({ children, variant = 'accent', className = '' }: TagProps) {
  const variants = {
    accent:
      'border-[#00ff88]/40 text-[#00ff88] shadow-[0_0_6px_rgba(0,255,136,0.25)] bg-[#00ff88]/5',
    secondary:
      'border-[#ff00ff]/40 text-[#ff00ff] shadow-[0_0_6px_rgba(255,0,255,0.25)] bg-[#ff00ff]/5',
    tertiary:
      'border-[#00d4ff]/40 text-[#00d4ff] shadow-[0_0_6px_rgba(0,212,255,0.25)] bg-[#00d4ff]/5',
    muted: 'border-[#2a2a3a] text-[#6b7280] bg-transparent',
  }

  return (
    <span
      className={`inline-flex items-center clip-card-sm border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.15em] font-[family-name:var(--font-label)] ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  )
}
