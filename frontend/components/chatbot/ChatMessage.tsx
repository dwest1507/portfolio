import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { UIMessage } from '@ai-sdk/react'

interface ChatMessageProps {
  message: UIMessage
}

function getTextContent(message: UIMessage): string {
  return message.parts
    .filter((p) => p.type === 'text')
    .map((p) => (p as { type: 'text'; text: string }).text)
    .join('')
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const text = getTextContent(message)

  if (!text) return null

  return (
    <div className={`flex gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <span className="mt-1 shrink-0 font-mono text-[10px] tracking-widest text-[#0ea5e9]">
          AI
        </span>
      )}

      <div
        className={`max-w-[85%] rounded-xl px-3 py-2 text-[13px] leading-relaxed ${
          isUser
            ? 'bg-[#0ea5e9]/15 text-[#ededef] shadow-[inset_0_0_0_1px_rgba(14,165,233,0.25)]'
            : 'bg-white/[0.05] text-[#ededef] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)]'
        }`}
      >
        {isUser ? (
          <span className="break-words whitespace-pre-wrap">{text}</span>
        ) : (
          <div className="text-[13px] leading-relaxed break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-white">{children}</strong>
                ),
                em: ({ children }) => <em className="text-[#ededef] italic">{children}</em>,
                blockquote: ({ children }) => (
                  <blockquote className="my-2 rounded-r border-l-2 border-[#0ea5e9]/60 bg-white/[0.03] py-1 pr-2 pl-3 text-[#ededef]/90 italic">
                    {children}
                  </blockquote>
                ),
                ul: ({ children }) => <ul className="my-2 ml-4 list-disc space-y-1">{children}</ul>,
                ol: ({ children }) => (
                  <ol className="my-2 ml-4 list-decimal space-y-1">{children}</ol>
                ),
                li: ({ children }) => <li className="pl-0.5 leading-relaxed">{children}</li>,
                h1: ({ children }) => (
                  <h1 className="mt-3 mb-1.5 text-[15px] font-semibold text-white first:mt-0">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-2.5 mb-1 text-[14px] font-semibold text-white first:mt-0">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mt-2 mb-1 text-[13.5px] font-medium text-white first:mt-0">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="mt-2 mb-1 text-[13px] font-medium text-white first:mt-0">
                    {children}
                  </h4>
                ),
                hr: () => <hr className="my-2.5 border-white/[0.08]" />,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#38bdf8] underline underline-offset-2 transition-colors hover:text-[#0ea5e9]"
                  >
                    {children}
                  </a>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline =
                    !className && typeof children === 'string' && !children.includes('\n')
                  if (isInline) {
                    return (
                      <code
                        className="rounded bg-white/10 px-1 py-0.5 font-mono text-[12px] text-[#38bdf8]"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  )
                },
                pre: ({ children }) => (
                  <pre className="my-2 overflow-x-auto rounded-lg border border-white/10 bg-black/40 p-2.5 font-mono text-xs text-[#38bdf8]">
                    {children}
                  </pre>
                ),
                table: ({ children }) => (
                  <div className="my-2 overflow-x-auto">
                    <table className="min-w-full divide-y divide-white/10 text-left text-[12px]">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="bg-white/[0.04] px-2.5 py-1 font-medium text-white">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="border-t border-white/[0.06] px-2.5 py-1">{children}</td>
                ),
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {isUser && (
        <span className="mt-1 shrink-0 font-mono text-[10px] tracking-widest text-[#8a8f98]">
          YOU
        </span>
      )}
    </div>
  )
}
