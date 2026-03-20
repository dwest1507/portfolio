'use client'

import type { FormEvent, ChangeEvent, KeyboardEvent } from 'react'

interface ChatInputProps {
  value: string
  onChange: (e: ChangeEvent<HTMLInputElement>) => void
  onSubmit: (e: FormEvent<HTMLFormElement>) => void
  disabled: boolean
  debounced: boolean
  limitReached: boolean
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled,
  debounced,
  limitReached,
}: ChatInputProps) {
  const isDisabled = disabled || debounced || limitReached

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isDisabled && value.trim()) {
        const form = e.currentTarget.closest('form')
        form?.requestSubmit()
      }
    }
  }

  const placeholder = limitReached
    ? 'Session limit reached (50 messages)'
    : debounced
      ? 'Please wait 3 seconds between messages...'
      : 'Ask about my experience or projects...'

  return (
    <form onSubmit={onSubmit} className="flex items-center gap-2">
      <div className="relative flex-1">
        {/* Terminal > prefix */}
        <span
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[13px] font-[family-name:var(--font-label)] text-[#00ff88]"
          aria-hidden="true"
        >
          &gt;
        </span>

        <input
          type="text"
          value={value}
          onChange={onChange}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder={placeholder}
          maxLength={500}
          autoComplete="off"
          spellCheck="false"
          aria-label="Chat message input"
          className="h-10 w-full clip-card-sm border border-[#2a2a3a] bg-[#0a0a0f] pl-8 pr-3 text-[13px] text-[#e0e0e0] placeholder-[#6b7280] transition-all duration-150 focus:border-[#00ff88] focus:shadow-[0_0_8px_rgba(0,255,136,0.25)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
        />
      </div>

      <button
        type="submit"
        disabled={isDisabled || !value.trim()}
        aria-label="Send message"
        className="h-10 w-10 shrink-0 clip-card-sm border border-[#00ff88] bg-transparent text-[#00ff88] transition-all duration-150 hover:bg-[#00ff88] hover:text-[#0a0a0f] hover:shadow-[0_0_12px_#00ff88] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-[#00ff88] disabled:hover:shadow-none"
      >
        {/* Send arrow icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="mx-auto h-4 w-4"
          aria-hidden="true"
        >
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22 11 13 2 9l20-7z" />
        </svg>
      </button>
    </form>
  )
}
