'use client'

import { useRef, useEffect, useState, type FormEvent, type ChangeEvent } from 'react'
import { useChat } from '@ai-sdk/react'
import { TextStreamChatTransport } from 'ai'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

const WELCOME_MESSAGE = "Hi! I'm David's AI assistant. Ask me anything about his experience, skills, or projects."
const SESSION_LIMIT = 50
const DEBOUNCE_MS = 3000

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [lastSubmitTime, setLastSubmitTime] = useState(0)
  const [debounced, setDebounced] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { messages, sendMessage, status, error, stop } = useChat({
    transport: new TextStreamChatTransport({ api: '/api/chat' }),
  })

  const isLoading = status === 'submitted' || status === 'streaming'

  // Count non-welcome user messages toward the limit
  const userMessageCount = messages.filter((m) => m.role === 'user').length
  const limitReached = userMessageCount >= SESSION_LIMIT

  // Scroll to bottom whenever messages change or streaming updates
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen, status])

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    }
  }, [])

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    setInputValue(e.target.value)
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()

    const text = inputValue.trim()
    if (!text || isLoading || debounced || limitReached) return

    const now = Date.now()
    if (now - lastSubmitTime < DEBOUNCE_MS) {
      setDebounced(true)
      const remaining = DEBOUNCE_MS - (now - lastSubmitTime)
      debounceTimerRef.current = setTimeout(() => setDebounced(false), remaining)
      return
    }

    sendMessage({ text })
    setInputValue('')
    setLastSubmitTime(now)

    // Re-arm debounce after sending
    setDebounced(true)
    debounceTimerRef.current = setTimeout(() => setDebounced(false), DEBOUNCE_MS)
  }

  // Streaming message text (assistant message being written right now)
  const streamingMessage = status === 'streaming' ? messages[messages.length - 1] : null
  const streamingText =
    streamingMessage?.role === 'assistant'
      ? streamingMessage.parts
          .filter((p) => p.type === 'text')
          .map((p) => (p as { type: 'text'; text: string }).text)
          .join('')
      : null

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? 'Close chat assistant' : 'Open chat assistant'}
        aria-expanded={isOpen}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center clip-card border-2 border-[#00ff88] bg-[#0a0a0f] text-[#00ff88] shadow-[0_0_12px_#00ff88,0_0_30px_rgba(0,255,136,0.3)] transition-all duration-150 hover:bg-[#00ff88] hover:text-[#0a0a0f] hover:shadow-[0_0_20px_#00ff88,0_0_50px_rgba(0,255,136,0.4)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff88]"
      >
        {isOpen ? (
          /* Close X */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
            aria-hidden="true"
          >
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        ) : (
          /* Chat bubble icon */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
            aria-hidden="true"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      <div
        role="dialog"
        aria-label="AI chat assistant"
        aria-hidden={!isOpen}
        className={`fixed bottom-24 right-6 z-50 flex flex-col clip-card border border-[#2a2a3a] bg-[#0a0a0f] shadow-[0_0_30px_rgba(0,255,136,0.08)] transition-all duration-200
          w-[calc(100vw-3rem)] sm:w-[400px]
          ${isOpen ? 'translate-y-0 opacity-100 pointer-events-auto' : 'translate-y-4 opacity-0 pointer-events-none'}
        `}
        style={{ height: '500px' }}
      >
        {/* Terminal header */}
        <div className="flex shrink-0 items-center gap-2 border-b border-[#2a2a3a] px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff3366] opacity-80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff9900] opacity-80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#00ff88] opacity-80" />
          <span className="ml-2 flex-1 text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#6b7280]">
            assistant.exe
          </span>
          {isLoading && (
            <button
              onClick={stop}
              aria-label="Stop generating"
              className="text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.15em] text-[#ff3366] hover:text-[#ff3366]/80 transition-colors"
            >
              ■ STOP
            </button>
          )}
        </div>

        {/* Message list */}
        <div
          className="flex flex-1 flex-col gap-3 overflow-y-auto p-4"
          aria-live="polite"
          aria-atomic="false"
          aria-relevant="additions"
        >
          {/* Welcome message */}
          <div className="flex justify-start gap-2">
            <span className="mt-1 shrink-0 text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#00ff88]">
              AI
            </span>
            <div className="max-w-[85%] clip-card-sm border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2 text-[13px] leading-relaxed text-[#e0e0e0]">
              <span>{WELCOME_MESSAGE}</span>
            </div>
          </div>

          {/* Chat messages */}
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Loading indicator — show when submitted but no streaming yet */}
          {status === 'submitted' && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#00ff88]">
                AI
              </span>
              <div className="clip-card-sm border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2">
                <span className="cursor-blink text-[13px] text-[#6b7280]" aria-label="Assistant is thinking" />
              </div>
            </div>
          )}

          {/* Streaming — append "..." if truncated on timeout (trailing cursor shown while streaming) */}
          {status === 'streaming' && streamingText === '' && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#00ff88]">
                AI
              </span>
              <div className="clip-card-sm border border-[#2a2a3a] bg-[#0a0a0f] px-3 py-2">
                <span className="cursor-blink text-[13px] text-[#6b7280]" />
              </div>
            </div>
          )}

          {/* Error state */}
          {status === 'error' && error && (
            <div className="flex justify-start gap-2">
              <span className="mt-1 shrink-0 text-[10px] font-[family-name:var(--font-label)] uppercase tracking-[0.2em] text-[#ff3366]">
                ERR
              </span>
              <div className="max-w-[85%] clip-card-sm border border-[#ff3366]/40 bg-[#0a0a0f] px-3 py-2 text-[13px] text-[#ff3366]">
                Sorry, I&apos;m having trouble responding right now. Please try again.
              </div>
            </div>
          )}

          {/* Session limit reached */}
          {limitReached && (
            <div className="text-center text-[11px] font-[family-name:var(--font-label)] uppercase tracking-[0.15em] text-[#6b7280]">
              — session limit reached —
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-[#2a2a3a] p-3">
          <ChatInput
            value={inputValue}
            onChange={handleInputChange}
            onSubmit={handleSubmit}
            disabled={isLoading}
            debounced={debounced}
            limitReached={limitReached}
          />
        </div>
      </div>
    </>
  )
}
