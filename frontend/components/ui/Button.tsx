import { type ReactNode, type ButtonHTMLAttributes } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost'
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
  'inline-flex items-center justify-center gap-2 text-sm font-medium transition-all duration-200 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0ea5e9] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506] disabled:opacity-40 disabled:pointer-events-none active:scale-[0.98]'

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-4 text-xs rounded-md',
  md: 'h-10 px-5 rounded-lg',
  lg: 'h-12 px-6 rounded-lg',
}

const variants: Record<ButtonVariant, string> = {
  primary:
    'bg-[#0ea5e9] text-[#082f49] shadow-[0_0_0_1px_rgba(14,165,233,0.5),0_4px_12px_rgba(14,165,233,0.25),inset_0_1px_0_0_rgba(255,255,255,0.15)] hover:bg-[#38bdf8] hover:shadow-[0_0_0_1px_rgba(14,165,233,0.6),0_4px_20px_rgba(14,165,233,0.4),inset_0_1px_0_0_rgba(255,255,255,0.15)]',
  secondary:
    'bg-white/[0.05] text-[#ededef] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.10)] hover:bg-white/[0.08] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]',
  outline:
    'bg-transparent text-[#ededef] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.10)] hover:shadow-[inset_0_0_0_1px_rgba(14,165,233,0.50)] hover:text-[#0ea5e9]',
  ghost: 'bg-transparent text-[#8a8f98] hover:bg-white/[0.05] hover:text-[#ededef]',
}

export default function Button({
  variant = 'primary',
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
