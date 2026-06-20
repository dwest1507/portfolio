'use client'

import { forwardRef } from 'react'
import type { FormEvent, ChangeEvent, KeyboardEvent } from 'react'

interface ChatInputProps {
  value: string
  onChange: (e: ChangeEvent<HTMLInputElement>) => void
  onSubmit: (e: FormEvent<HTMLFormElement>) => void
  disabled: boolean
  debounced: boolean
  limitReached: boolean
}

const ChatInput = forwardRef<HTMLInputElement, ChatInputProps>(function ChatInput(
  { value, onChange, onSubmit, disabled, debounced, limitReached },
  ref,
) {
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
      ? 'Please wait a moment...'
      : 'Ask about my experience or projects...'

  return (
    <form onSubmit={onSubmit} className="flex items-center gap-2">
      <input
        ref={ref}
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
        className="h-10 w-full flex-1 rounded-lg border border-white/[0.08] bg-white/[0.04] px-4 text-[13px] text-[#ededef] placeholder-[#8a8f98]/60 transition-all duration-150 focus:border-[#0ea5e9]/50 focus:bg-white/[0.06] focus:outline-none focus:shadow-[0_0_0_3px_rgba(14,165,233,0.15)] disabled:cursor-not-allowed disabled:opacity-40"
      />

      <button
        type="submit"
        disabled={isDisabled || !value.trim()}
        aria-label="Send message"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0ea5e9] text-white shadow-[0_0_0_1px_rgba(14,165,233,0.5),0_2px_8px_rgba(14,165,233,0.3)] transition-all duration-150 hover:bg-[#38bdf8] active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-[#0ea5e9]"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22 11 13 2 9l20-7z" />
        </svg>
      </button>
    </form>
  )
})

export default ChatInput
