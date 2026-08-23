import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ChatInput from '@/components/chatbot/ChatInput'

const baseProps = {
  value: '',
  onChange: vi.fn(),
  onSubmit: vi.fn((e: React.FormEvent) => e.preventDefault()),
  disabled: false,
  debounced: false,
  limitReached: false,
}

describe('ChatInput', () => {
  it('disables the send button when the input is empty', () => {
    render(<ChatInput {...baseProps} value="" />)
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
  })

  it('disables the send button for whitespace-only input', () => {
    render(<ChatInput {...baseProps} value="   " />)
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
  })

  it('enables the send button when there is text', () => {
    render(<ChatInput {...baseProps} value="Hello" />)
    expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled()
  })

  it('submits the form when Enter is pressed with text', async () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault())
    const user = userEvent.setup()
    render(<ChatInput {...baseProps} value="Hello" onSubmit={onSubmit} />)

    await user.type(screen.getByRole('textbox'), '{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('does not submit on Enter when the input is empty', async () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault())
    const user = userEvent.setup()
    render(<ChatInput {...baseProps} value="" onSubmit={onSubmit} />)

    await user.type(screen.getByRole('textbox'), '{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('disables the input while a response is loading', () => {
    render(<ChatInput {...baseProps} disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('shows the wait placeholder while debounced', () => {
    render(<ChatInput {...baseProps} debounced />)
    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    expect(input).toHaveAttribute('placeholder', 'Please wait a moment...')
  })

  it('shows the limit placeholder when the session limit is reached', () => {
    render(<ChatInput {...baseProps} limitReached />)
    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
    expect(input).toHaveAttribute('placeholder', 'Session limit reached (50 messages)')
  })

  it('caps input length at 500 characters', () => {
    render(<ChatInput {...baseProps} />)
    expect(screen.getByRole('textbox')).toHaveAttribute('maxLength', '500')
  })
})
