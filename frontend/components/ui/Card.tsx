'use client'

import { type ReactNode, useRef, useState } from 'react'

interface CardProps {
  children: ReactNode
  variant?: 'default' | 'glass' | 'elevated'
  spotlight?: boolean
  className?: string
}

export default function Card({
  children,
  variant = 'default',
  spotlight = false,
  className = '',
}: CardProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [spotPos, setSpotPos] = useState({ x: 0, y: 0 })
  const [spotVisible, setSpotVisible] = useState(false)

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!spotlight || !cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    setSpotPos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  const variants: Record<'default' | 'glass' | 'elevated', string> = {
    default:
      'bg-gradient-to-b from-white/[0.08] to-white/[0.02] shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_2px_20px_rgba(0,0,0,0.4)]',
    glass:
      'bg-white/[0.03] backdrop-blur-xl shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_8px_32px_rgba(0,0,0,0.3)]',
    elevated:
      'bg-gradient-to-b from-white/[0.10] to-white/[0.04] shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_8px_40px_rgba(0,0,0,0.5),0_0_80px_rgba(14,165,233,0.06)]',
  }

  return (
    <div
      ref={cardRef}
      className={`relative overflow-hidden rounded-2xl border border-white/[0.06] ${variants[variant]} ${className}`}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setSpotVisible(true)}
      onMouseLeave={() => setSpotVisible(false)}
    >
      {spotlight && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-10 transition-opacity duration-300"
          style={{
            opacity: spotVisible ? 1 : 0,
            background: `radial-gradient(300px circle at ${spotPos.x}px ${spotPos.y}px, rgba(14,165,233,0.12), transparent)`,
          }}
        />
      )}
      {children}
    </div>
  )
}
