import { type ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  variant?: 'default' | 'terminal' | 'holographic'
  hoverEffect?: boolean
  className?: string
  title?: string // used for terminal variant header label
}

export default function Card({
  children,
  variant = 'default',
  hoverEffect = false,
  className = '',
  title,
}: CardProps) {
  if (variant === 'terminal') {
    return (
      <div
        className={`clip-card relative border border-[#2a2a3a] bg-[#0a0a0f] ${hoverEffect ? 'neon-border-hover transition-all duration-300 hover:-translate-y-px hover:border-[#00ff88]' : ''} ${className}`}
      >
        {/* Terminal header bar */}
        <div className="flex items-center gap-2 border-b border-[#2a2a3a] px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff3366] opacity-80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff9900] opacity-80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#00ff88] opacity-80" />
          {title && (
            <span className="ml-2 text-[10px] uppercase tracking-[0.2em] text-[#6b7280] font-[family-name:var(--font-label)]">
              {title}
            </span>
          )}
        </div>
        <div className="p-6">{children}</div>
      </div>
    )
  }

  if (variant === 'holographic') {
    return (
      <div
        className={`clip-card relative border border-[#00ff88]/25 bg-[#1c1c2e]/40 shadow-[0_0_20px_rgba(0,255,136,0.1),inset_0_0_20px_rgba(0,255,136,0.03)] backdrop-blur-sm ${hoverEffect ? 'neon-border-hover transition-all duration-300 hover:-translate-y-px hover:shadow-[0_0_30px_rgba(0,255,136,0.25)]' : ''} ${className}`}
      >
        {/* Corner accents */}
        <span className="pointer-events-none absolute left-0 top-0 h-4 w-4 border-l-2 border-t-2 border-[#00ff88]" />
        <span className="pointer-events-none absolute right-0 top-0 h-4 w-4 border-r-2 border-t-2 border-[#00ff88]" />
        <span className="pointer-events-none absolute bottom-0 left-0 h-4 w-4 border-b-2 border-l-2 border-[#00ff88]" />
        <span className="pointer-events-none absolute bottom-0 right-0 h-4 w-4 border-b-2 border-r-2 border-[#00ff88]" />
        <div className="p-6">{children}</div>
      </div>
    )
  }

  // default
  return (
    <div
      className={`clip-card border border-[#2a2a3a] bg-[#12121a] ${hoverEffect ? 'neon-border-hover transition-all duration-300 hover:-translate-y-px hover:border-[#00ff88]' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
