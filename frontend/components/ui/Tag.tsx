import { type ReactNode } from 'react'

interface TagProps {
  children: ReactNode
  variant?: 'default' | 'accent' | 'muted'
  className?: string
}

export default function Tag({ children, variant = 'default', className = '' }: TagProps) {
  const variants = {
    default: 'border-white/[0.10] text-[#8a8f98]',
    accent: 'border-[#0ea5e9]/30 text-[#0ea5e9] bg-[#0ea5e9]/5',
    muted: 'border-white/[0.06] text-[#8a8f98]/60',
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[10px] tracking-widest ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  )
}
