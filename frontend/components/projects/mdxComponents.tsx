import type { ReactNode, HTMLAttributes, AnchorHTMLAttributes } from 'react'

// ─── Shared primitives ───────────────────────────────────────────────────────

type Block = HTMLAttributes<HTMLElement> & { children?: ReactNode }
type Anchor = AnchorHTMLAttributes<HTMLAnchorElement> & { children?: ReactNode }
type Code = HTMLAttributes<HTMLElement> & { children?: ReactNode; className?: string }

// ─── Heading separators ───────────────────────────────────────────────────────

function H2({ children, ...props }: Block) {
  return (
    <div className="mb-6 mt-14 first:mt-0">
      <div className="mb-3 flex items-baseline gap-3">
        <span
          aria-hidden
          className="font-[family-name:var(--font-label)] text-sm text-[#00ff88]"
        >
          &gt;
        </span>
        <h2
          className="font-[family-name:var(--font-heading)] text-lg font-bold uppercase tracking-widest text-[#e0e0e0]"
          {...(props as HTMLAttributes<HTMLHeadingElement>)}
        >
          {children}
          <span aria-hidden className="ml-1 text-[#00ff88]">
            _
          </span>
        </h2>
      </div>
      <div
        aria-hidden
        className="h-px bg-gradient-to-r from-[#00ff88]/50 via-[#2a2a3a]/80 to-transparent"
      />
    </div>
  )
}

function H3({ children, ...props }: Block) {
  return (
    <h3
      className="mb-3 mt-8 flex items-baseline gap-2 font-[family-name:var(--font-heading)] text-sm font-semibold uppercase tracking-wide text-[#00d4ff]"
      {...(props as HTMLAttributes<HTMLHeadingElement>)}
    >
      <span aria-hidden className="text-[#6b7280]">
        //
      </span>
      {children}
    </h3>
  )
}

// ─── Prose ────────────────────────────────────────────────────────────────────

function P({ children, ...props }: Block) {
  return (
    <p
      className="mb-5 font-[family-name:var(--font-body)] text-sm leading-7 text-[#a0a0a8]"
      {...(props as HTMLAttributes<HTMLParagraphElement>)}
    >
      {children}
    </p>
  )
}

function Blockquote({ children, ...props }: Block) {
  return (
    <blockquote
      className="my-6 border-l-2 border-[#00ff88]/50 pl-5 font-[family-name:var(--font-body)] text-sm italic text-[#6b7280]"
      {...(props as HTMLAttributes<HTMLQuoteElement>)}
    >
      {children}
    </blockquote>
  )
}

function Strong({ children, ...props }: Block) {
  return (
    <strong className="font-bold text-[#e0e0e0]" {...(props as HTMLAttributes<HTMLElement>)}>
      {children}
    </strong>
  )
}

function Em({ children, ...props }: Block) {
  return (
    <em className="italic text-[#00d4ff]" {...(props as HTMLAttributes<HTMLElement>)}>
      {children}
    </em>
  )
}

// ─── Lists ────────────────────────────────────────────────────────────────────

function Ul({ children, ...props }: Block) {
  return (
    <ul
      className="mb-5 space-y-1.5 pl-5 list-disc marker:text-[#00ff88]"
      {...(props as HTMLAttributes<HTMLUListElement>)}
    >
      {children}
    </ul>
  )
}

function Ol({ children, ...props }: Block) {
  return (
    <ol
      className="mb-5 space-y-1.5 pl-5 list-decimal marker:text-[#00ff88] marker:font-[family-name:var(--font-label)] marker:text-xs"
      {...(props as HTMLAttributes<HTMLOListElement>)}
    >
      {children}
    </ol>
  )
}

function Li({ children, ...props }: Block) {
  return (
    <li
      className="font-[family-name:var(--font-body)] text-sm leading-7 text-[#a0a0a8] pl-1"
      {...(props as HTMLAttributes<HTMLLIElement>)}
    >
      {children}
    </li>
  )
}

// ─── Code ─────────────────────────────────────────────────────────────────────

function Code({ children, className, ...props }: Code) {
  const isBlock = Boolean(className?.startsWith('language-'))
  if (isBlock) {
    return (
      <code
        className={`font-[family-name:var(--font-body)] text-[#00ff88] ${className ?? ''}`}
        {...(props as HTMLAttributes<HTMLElement>)}
      >
        {children}
      </code>
    )
  }
  return (
    <code
      className="rounded-sm border border-[#2a2a3a] bg-[#1c1c2e] px-1.5 py-0.5 font-[family-name:var(--font-body)] text-[0.85em] text-[#00ff88]"
      {...(props as HTMLAttributes<HTMLElement>)}
    >
      {children}
    </code>
  )
}

function Pre({ children, ...props }: Block) {
  return (
    <div className="clip-card my-6 overflow-hidden border border-[#2a2a3a]">
      {/* Terminal header */}
      <div className="flex items-center gap-1.5 border-b border-[#2a2a3a] bg-[#1c1c2e] px-4 py-2.5">
        <div className="h-2.5 w-2.5 rounded-full bg-[#ff3366]" />
        <div className="h-2.5 w-2.5 rounded-full bg-[#ff8800]" />
        <div className="h-2.5 w-2.5 rounded-full bg-[#00ff88]" />
        <span className="ml-auto font-[family-name:var(--font-label)] text-[8px] uppercase tracking-[0.3em] text-[#6b7280]">
          TERMINAL
        </span>
      </div>
      <pre
        className="overflow-x-auto bg-[#0a0a0f] p-5 font-[family-name:var(--font-body)] text-sm leading-relaxed"
        {...(props as HTMLAttributes<HTMLPreElement>)}
      >
        {children}
      </pre>
    </div>
  )
}

// ─── Links ────────────────────────────────────────────────────────────────────

function A({ href, children, ...props }: Anchor) {
  const isExternal = href?.startsWith('http')
  return (
    <a
      href={href}
      target={isExternal ? '_blank' : undefined}
      rel={isExternal ? 'noopener noreferrer' : undefined}
      className="text-[#00ff88] underline decoration-[#00ff88]/30 underline-offset-4 transition-all duration-150 hover:decoration-[#00ff88]"
      {...props}
    >
      {children}
    </a>
  )
}

// ─── Divider ─────────────────────────────────────────────────────────────────

function Hr() {
  return (
    <div aria-hidden className="my-10 flex items-center gap-4">
      <div className="h-px flex-1 bg-gradient-to-r from-transparent to-[#2a2a3a]" />
      <span className="font-[family-name:var(--font-label)] text-[8px] uppercase tracking-[0.4em] text-[#2a2a3a]">
        ◆
      </span>
      <div className="h-px flex-1 bg-gradient-to-l from-transparent to-[#2a2a3a]" />
    </div>
  )
}

// ─── Exports ─────────────────────────────────────────────────────────────────

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
