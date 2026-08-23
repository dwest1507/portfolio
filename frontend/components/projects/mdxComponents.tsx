import type { ReactNode, HTMLAttributes, AnchorHTMLAttributes } from 'react'

type Block = HTMLAttributes<HTMLElement> & { children?: ReactNode }
type Anchor = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode }
type Code = HTMLAttributes<HTMLElement> & { children?: ReactNode; className?: string }

function H2({ children, ...props }: Block) {
  return (
    <div className="mt-14 mb-6 first:mt-0">
      <h2
        className="text-xl font-semibold tracking-tight text-[#ededef]"
        {...(props as HTMLAttributes<HTMLHeadingElement>)}
      >
        {children}
      </h2>
      <div
        aria-hidden
        className="mt-3 h-px bg-gradient-to-r from-[#0ea5e9]/30 via-white/[0.06] to-transparent"
      />
    </div>
  )
}

function H3({ children, ...props }: Block) {
  return (
    <h3
      className="mt-8 mb-3 text-base font-medium text-[#ededef]"
      {...(props as HTMLAttributes<HTMLHeadingElement>)}
    >
      {children}
    </h3>
  )
}

function P({ children, ...props }: Block) {
  return (
    <p
      className="mb-5 text-sm leading-7 text-[#8a8f98]"
      {...(props as HTMLAttributes<HTMLParagraphElement>)}
    >
      {children}
    </p>
  )
}

function Blockquote({ children, ...props }: Block) {
  return (
    <blockquote
      className="my-6 border-l-2 border-[#0ea5e9]/40 pl-5 text-sm text-[#8a8f98] italic"
      {...(props as HTMLAttributes<HTMLQuoteElement>)}
    >
      {children}
    </blockquote>
  )
}

function Strong({ children, ...props }: Block) {
  return (
    <strong className="font-semibold text-[#ededef]" {...(props as HTMLAttributes<HTMLElement>)}>
      {children}
    </strong>
  )
}

function Em({ children, ...props }: Block) {
  return (
    <em className="text-[#ededef]/80 italic" {...(props as HTMLAttributes<HTMLElement>)}>
      {children}
    </em>
  )
}

function Ul({ children, ...props }: Block) {
  return (
    <ul
      className="mb-5 list-disc space-y-1.5 pl-5 marker:text-[#0ea5e9]"
      {...(props as HTMLAttributes<HTMLUListElement>)}
    >
      {children}
    </ul>
  )
}

function Ol({ children, ...props }: Block) {
  return (
    <ol
      className="mb-5 list-decimal space-y-1.5 pl-5 marker:font-mono marker:text-xs marker:text-[#8a8f98]"
      {...(props as HTMLAttributes<HTMLOListElement>)}
    >
      {children}
    </ol>
  )
}

function Li({ children, ...props }: Block) {
  return (
    <li
      className="pl-1 text-sm leading-7 text-[#8a8f98]"
      {...(props as HTMLAttributes<HTMLLIElement>)}
    >
      {children}
    </li>
  )
}

function Code({ children, className, ...props }: Code) {
  const isBlock = Boolean(className?.startsWith('language-'))
  if (isBlock) {
    return (
      <code
        className={`text-[#0ea5e9] ${className ?? ''}`}
        {...(props as HTMLAttributes<HTMLElement>)}
      >
        {children}
      </code>
    )
  }
  return (
    <code
      className="rounded border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 font-mono text-[0.85em] text-[#0ea5e9]"
      {...(props as HTMLAttributes<HTMLElement>)}
    >
      {children}
    </code>
  )
}

function Pre({ children, ...props }: Block) {
  return (
    <div className="my-6 overflow-hidden rounded-xl border border-white/[0.06] shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
      <div className="flex items-center border-b border-white/[0.06] bg-white/[0.03] px-4 py-2.5">
        <div className="flex gap-1.5">
          <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
          <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
          <div className="h-2.5 w-2.5 rounded-full bg-white/[0.08]" />
        </div>
        <span className="ml-auto font-mono text-[8px] tracking-[0.3em] text-[#8a8f98]/40">
          CODE
        </span>
      </div>
      <pre
        className="overflow-x-auto bg-[#0a0a0c] p-5 font-mono text-sm leading-relaxed"
        {...(props as HTMLAttributes<HTMLPreElement>)}
      >
        {children}
      </pre>
    </div>
  )
}

function A({ href, children, ...props }: Anchor) {
  const isExternal = href?.startsWith('http')
  return (
    <a
      href={href}
      target={isExternal ? '_blank' : undefined}
      rel={isExternal ? 'noopener noreferrer' : undefined}
      className="text-[#0ea5e9] underline decoration-[#0ea5e9]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#0ea5e9]"
      {...props}
    >
      {children}
    </a>
  )
}

function Hr() {
  return (
    <div aria-hidden className="my-10">
      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
    </div>
  )
}

export const mdxComponents = {
  h2: H2,
  h3: H3,
  p: P,
  blockquote: Blockquote,
  strong: Strong,
  em: Em,
  ul: Ul,
  ol: Ol,
  li: Li,
  code: Code,
  pre: Pre,
  a: A,
  hr: Hr,
}
