import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { UIMessage } from '@ai-sdk/react'
import ChatMessage from '@/components/chatbot/ChatMessage'

function makeMessage(role: 'user' | 'assistant', texts: string[]): UIMessage {
  return {
    id: 'test-id',
    role,
    parts: texts.map((text) => ({ type: 'text' as const, text })),
  } as UIMessage
}

describe('ChatMessage', () => {
  it('renders a user message with the YOU label', () => {
    render(<ChatMessage message={makeMessage('user', ['Hello there'])} />)
    expect(screen.getByText('Hello there')).toBeInTheDocument()
    expect(screen.getByText('YOU')).toBeInTheDocument()
    expect(screen.queryByText('AI')).not.toBeInTheDocument()
  })

  it('renders an assistant message with the AI label', () => {
    render(<ChatMessage message={makeMessage('assistant', ['Hi, I can help.'])} />)
    expect(screen.getByText('Hi, I can help.')).toBeInTheDocument()
    expect(screen.getByText('AI')).toBeInTheDocument()
    expect(screen.queryByText('YOU')).not.toBeInTheDocument()
  })

  it('joins multiple text parts into one message', () => {
    render(<ChatMessage message={makeMessage('assistant', ['Hello ', 'world'])} />)
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders nothing when the message has no text content', () => {
    const { container } = render(<ChatMessage message={makeMessage('assistant', [])} />)
    expect(container).toBeEmptyDOMElement()
  })
})
