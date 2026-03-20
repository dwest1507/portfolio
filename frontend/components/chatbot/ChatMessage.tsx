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
        <span className="mt-1 shrink-0 text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#00ff88]">
          AI
        </span>
      )}

      <div
        className={`max-w-[85%] px-3 py-2 text-[13px] leading-relaxed clip-card-sm ${
          isUser
            ? 'border border-[#00d4ff]/40 bg-[#1c1c2e] text-[#00d4ff] shadow-[0_0_8px_rgba(0,212,255,0.12)]'
            : 'border border-[#2a2a3a] bg-[#0a0a0f] text-[#e0e0e0]'
        }`}
      >
        <span className="whitespace-pre-wrap break-words">{text}</span>
      </div>

      {isUser && (
        <span className="mt-1 shrink-0 text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#00d4ff]">
          YOU
        </span>
      )}
    </div>
  )
}
