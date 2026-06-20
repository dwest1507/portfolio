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
        <span className="whitespace-pre-wrap break-words">{text}</span>
      </div>

      {isUser && (
        <span className="mt-1 shrink-0 font-mono text-[10px] tracking-widest text-[#8a8f98]">
          YOU
        </span>
      )}
    </div>
  )
}
