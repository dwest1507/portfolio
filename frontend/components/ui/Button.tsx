import { type ReactNode, type ButtonHTMLAttributes } from 'react'

type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'glitch'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonBaseProps {
  variant?: ButtonVariant
  size?: ButtonSize
  children: ReactNode
  className?: string
}

type ButtonAsButton = ButtonBaseProps &
  ButtonHTMLAttributes<HTMLButtonElement> & { href?: never; target?: never; rel?: never }

type ButtonAsAnchor = ButtonBaseProps & {
  href: string
  target?: string
  rel?: string
  onClick?: never
  type?: never
  disabled?: never
}

type ButtonProps = ButtonAsButton | ButtonAsAnchor

const base =
  'inline-flex items-center justify-center gap-2 font-[family-name:var(--font-label)] text-xs uppercase tracking-[0.2em] transition-all duration-150 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff88] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f] disabled:opacity-40 disabled:pointer-events-none'

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-4 text-[10px]',
  md: 'h-10 px-6',
  lg: 'h-12 px-8 text-sm',
}

const variants: Record<ButtonVariant, string> = {
  default:
    'clip-card-sm border-2 border-[#00ff88] text-[#00ff88] bg-transparent hover:bg-[#00ff88] hover:text-[#0a0a0f] hover:shadow-[0_0_12px_#00ff88,0_0_30px_rgba(0,255,136,0.4)]',
  secondary:
    'clip-card-sm border-2 border-[#ff00ff] text-[#ff00ff] bg-transparent hover:bg-[#ff00ff] hover:text-[#0a0a0f] hover:shadow-[0_0_12px_#ff00ff,0_0_30px_rgba(255,0,255,0.4)]',
  outline:
    'clip-card-sm border border-[#2a2a3a] text-[#e0e0e0] bg-transparent hover:border-[#00ff88] hover:text-[#00ff88] hover:shadow-[0_0_8px_rgba(0,255,136,0.3)]',
  ghost:
    'border-0 text-[#6b7280] bg-transparent hover:bg-[#00ff88]/10 hover:text-[#00ff88]',
  glitch:
    'clip-card-sm border-2 border-[#00ff88] bg-[#00ff88] text-[#0a0a0f] font-bold hover:brightness-110 hover:shadow-[0_0_16px_#00ff88,0_0_40px_rgba(0,255,136,0.5)] glitch-animate',
}

export default function Button({
  variant = 'default',
  size = 'md',
  children,
  className = '',
  href,
  target,
  rel,
  ...props
}: ButtonProps) {
  const classes = `${base} ${sizes[size]} ${variants[variant]} ${className}`

  if (href !== undefined) {
    return (
      <a href={href} target={target} rel={rel} className={classes}>
        {children}
      </a>
    )
  }

  return (
    <button className={classes} {...(props as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {children}
    </button>
  )
}
