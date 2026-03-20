'use client'

interface FilterBarProps {
  tags: string[]
  active: string
  onChange: (tag: string) => void
}

export default function FilterBar({ tags, active, onChange }: FilterBarProps) {
  return (
    <div
      role="group"
      aria-label="Filter projects by technology"
      className="flex flex-wrap gap-2"
    >
      {tags.map((tag) => {
        const isActive = tag === active
        return (
          <button
            key={tag}
            onClick={() => onChange(tag)}
            aria-pressed={isActive}
            className={`clip-card-sm border px-3 py-1.5 font-[family-name:var(--font-label)] text-[10px] uppercase tracking-[0.2em] transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff88] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f] min-h-[36px] ${
              isActive
                ? 'border-[#00ff88] bg-[#00ff88] text-[#0a0a0f] shadow-[0_0_10px_rgba(0,255,136,0.4)]'
                : 'border-[#2a2a3a] bg-transparent text-[#6b7280] hover:border-[#00ff88]/50 hover:text-[#00ff88]'
            }`}
          >
            {tag}
          </button>
        )
      })}
    </div>
  )
}
