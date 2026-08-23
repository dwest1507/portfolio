'use client'

interface FilterBarProps {
  tags: string[]
  active: string
  onChange: (tag: string) => void
}

export default function FilterBar({ tags, active, onChange }: FilterBarProps) {
  return (
    <div role="group" aria-label="Filter projects by technology" className="flex flex-wrap gap-2">
      {tags.map((tag) => {
        const isActive = tag === active
        return (
          <button
            key={tag}
            onClick={() => onChange(tag)}
            aria-pressed={isActive}
            className={`min-h-[36px] rounded-full border px-4 py-1.5 font-mono text-[11px] tracking-widest transition-all duration-200 focus-visible:ring-2 focus-visible:ring-[#0ea5e9] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506] focus-visible:outline-none ${
              isActive
                ? 'border-[#0ea5e9]/50 bg-[#0ea5e9]/10 text-[#0ea5e9] shadow-[0_0_0_1px_rgba(14,165,233,0.3)]'
                : 'border-white/[0.08] bg-transparent text-[#8a8f98] hover:border-white/[0.14] hover:text-[#ededef]'
            }`}
          >
            {tag}
          </button>
        )
      })}
    </div>
  )
}
