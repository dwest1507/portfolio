'use client'

import { useRef, useEffect, useState, type FormEvent, type ChangeEvent } from 'react'
import Link from 'next/link'
import { useChat } from '@ai-sdk/react'
import { TextStreamChatTransport } from 'ai'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

const WELCOME_MESSAGE =
  "Hi! I'm David's AI assistant. Ask me anything about his experience, skills, or projects."
const SESSION_LIMIT = 50
const DEBOUNCE_MS = 3000

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [lastSubmitTime, setLastSubmitTime] = useState(0)
  const [debounced, setDebounced] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tooltipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Show tooltip after 3s, auto-hide after 8s; only once per session
  useEffect(() => {
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('chatTooltipSeen')) return
    const show = setTimeout(() => {
      setShowTooltip(true)
      tooltipTimerRef.current = setTimeout(() => setShowTooltip(false), 8000)
    }, 4000)
    return () => {
      clearTimeout(show)
      if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current)
    }
  }, [])

  const { messages, sendMessage, status, error, stop } = useChat({
    transport: new TextStreamChatTransport({ api: '/api/chat' }),
  })

  const isLoading = status === 'submitted' || status === 'streaming'

  const userMessageCount = messages.filter((m) => m.role === 'user').length
  const limitReached = userMessageCount >= SESSION_LIMIT

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen, status])

  useEffect(() => {
    if (!isLoading && !debounced && !limitReached && isOpen) {
      inputRef.current?.focus()
    }
  }, [isLoading, debounced, limitReached, isOpen])

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
      if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current)
    }
  }, [])

  function dismissTooltip() {
    setShowTooltip(false)
    if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current)
    if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('chatTooltipSeen', '1')
  }

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
    inputRef.current?.focus()

    setDebounced(true)
    debounceTimerRef.current = setTimeout(() => setDebounced(false), DEBOUNCE_MS)
  }

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
      {/* Tooltip bubble */}
      <div
        aria-hidden={!showTooltip}
        inert={!showTooltip}
        className={`fixed right-6 bottom-24 z-50 flex items-start gap-2 transition-all duration-200 ${
          showTooltip
            ? 'pointer-events-auto translate-y-0 opacity-100'
            : 'pointer-events-none translate-y-2 opacity-0'
        }`}
      >
        <div className="rounded-xl border border-white/[0.08] bg-[#0a0a0c]/95 px-3 py-2 shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_8px_32px_rgba(0,0,0,0.4)] backdrop-blur-xl">
          <p className="text-[12px] text-[#ededef]">Ask my AI assistant about my qualifications</p>
        </div>
        <button
          onClick={dismissTooltip}
          aria-label="Dismiss tooltip"
          className="mt-1 shrink-0 text-[#8a8f98] transition-colors hover:text-[#ededef]"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="h-3.5 w-3.5"
            aria-hidden="true"
          >
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Floating trigger button */}
      <div className="fixed right-6 bottom-6 z-50">
        {/* Pulse ring — visible when closed */}
        {!isOpen && (
          <span
            aria-hidden="true"
            className="absolute inset-0 animate-ping rounded-full bg-[#0ea5e9] opacity-20"
          />
        )}
        <button
          onClick={() => {
            setIsOpen((prev) => !prev)
            dismissTooltip()
          }}
          aria-label={isOpen ? 'Close chat assistant' : 'Open chat assistant'}
          aria-expanded={isOpen}
          className="relative flex h-14 w-14 items-center justify-center rounded-full bg-[#0ea5e9] text-[#082f49] shadow-[0_0_0_1px_rgba(14,165,233,0.5),0_4px_20px_rgba(14,165,233,0.4)] transition-all duration-200 hover:bg-[#38bdf8] hover:shadow-[0_0_0_1px_rgba(14,165,233,0.6),0_4px_30px_rgba(14,165,233,0.5)] focus-visible:ring-2 focus-visible:ring-[#0ea5e9] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050506] focus-visible:outline-none active:scale-[0.97]"
        >
          {isOpen ? (
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
      </div>

      {/* Chat panel */}
      <div
        role="dialog"
        aria-label="AI chat assistant"
        aria-hidden={!isOpen}
        inert={!isOpen}
        className={`fixed right-6 bottom-24 z-50 flex w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/95 shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_8px_40px_rgba(0,0,0,0.6)] backdrop-blur-xl transition-all duration-200 sm:w-[400px] ${
          isOpen
            ? 'pointer-events-auto translate-y-0 opacity-100'
            : 'pointer-events-none translate-y-4 opacity-0'
        }`}
        style={{ height: '500px' }}
      >
        {/* Panel header */}
        <div className="relative flex shrink-0 items-center gap-3 border-b border-white/[0.06] px-4 py-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0ea5e9]/15">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-3.5 w-3.5 text-[#0ea5e9]"
              aria-hidden="true"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-[#ededef]">AI Assistant</p>
            <p className="font-mono text-[10px] tracking-widest text-[#8a8f98]">David West</p>
          </div>
          {isLoading && (
            <button
              onClick={stop}
              aria-label="Stop generating"
              className="ml-auto rounded-md border border-white/[0.08] px-2.5 py-1 font-mono text-[10px] tracking-widest text-[#8a8f98] transition-colors hover:text-[#ededef]"
            >
              Stop
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
            <span className="mt-1 shrink-0 font-mono text-[10px] tracking-widest text-[#0ea5e9]">
              AI
            </span>
            <div className="max-w-[85%] rounded-xl bg-white/[0.05] px-3 py-2 text-[13px] leading-relaxed text-[#ededef] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)]">
              {WELCOME_MESSAGE}
              {/* Connects the demo to the engineering behind it: the retrieval
                  pipeline and its eval suite are written up as a project. */}
              <Link
                href="/projects/portfolio"
                className="mt-2 block font-mono text-[10px] tracking-widest text-[#0ea5e9] transition-colors duration-150 hover:text-[#38bdf8]"
              >
                How this works →
              </Link>
            </div>
          </div>

          {/* Chat messages */}
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Loading indicator */}
          {status === 'submitted' && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] tracking-widest text-[#0ea5e9]">AI</span>
              <div className="rounded-xl bg-white/[0.05] px-3 py-2 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)]">
                <span
                  className="inline-block h-3 w-3 animate-[blink_1s_step-end_infinite] text-[13px] text-[#8a8f98]"
                  aria-label="Assistant is thinking"
                >
                  ●
                </span>
              </div>
            </div>
          )}

          {/* Streaming — show cursor while empty */}
          {status === 'streaming' && streamingText === '' && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] tracking-widest text-[#0ea5e9]">AI</span>
              <div className="rounded-xl bg-white/[0.05] px-3 py-2 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)]">
                <span className="inline-block h-3 animate-[blink_1s_step-end_infinite] text-[13px] text-[#8a8f98]">
                  ●
                </span>
              </div>
            </div>
          )}

          {/* Error state */}
          {status === 'error' && error && (
            <div className="flex justify-start gap-2">
              <span className="mt-1 shrink-0 font-mono text-[10px] tracking-widest text-red-400">
                ERR
              </span>
              <div className="max-w-[85%] rounded-xl bg-red-500/5 px-3 py-2 text-[13px] text-red-400 shadow-[inset_0_0_0_1px_rgba(239,68,68,0.2)]">
                Sorry, I&apos;m having trouble responding right now. Please try again.
              </div>
            </div>
          )}

          {/* Session limit reached */}
          {limitReached && (
            <div className="text-center font-mono text-[11px] tracking-widest text-[#8a8f98]">
              — session limit reached —
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-white/[0.06] p-3">
          <ChatInput
            ref={inputRef}
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
