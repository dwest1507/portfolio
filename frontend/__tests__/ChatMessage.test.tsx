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

  it('safely escapes raw HTML and prevents script/image tag injection', () => {
    const malicious = 'Test <script>alert("xss")</script><img src=x onerror=alert(1)> markup'
    const { container } = render(<ChatMessage message={makeMessage('assistant', [malicious])} />)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })

  it('renders bold, italic, and bold-italic markdown formatting', () => {
    const markdown =
      '***Featured Project***: Developed a **scalable backend** with *high throughput*.'
    const { container } = render(<ChatMessage message={makeMessage('assistant', [markdown])} />)

    const strongElements = container.querySelectorAll('strong')
    expect(strongElements.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Featured Project')).toBeInTheDocument()
    expect(screen.getByText('scalable backend')).toBeInTheDocument()

    const emElements = container.querySelectorAll('em')
    expect(emElements.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('high throughput')).toBeInTheDocument()
  })

  it('renders blockquotes, lists, inline code, and external links', () => {
    const markdown = `> Building full-stack systems.

Core skills:
1. **TypeScript & React**
2. **Python & FastAPI**

Check \`git log\` or visit [GitHub](https://github.com).`

    const { container } = render(<ChatMessage message={makeMessage('assistant', [markdown])} />)

    const blockquote = container.querySelector('blockquote')
    expect(blockquote).not.toBeNull()
    expect(blockquote?.textContent).toContain('Building full-stack systems.')

    const ol = container.querySelector('ol')
    expect(ol).not.toBeNull()
    expect(ol?.querySelectorAll('li').length).toBe(2)
    expect(screen.getByText('TypeScript & React')).toBeInTheDocument()

    const code = container.querySelector('code')
    expect(code?.textContent).toBe('git log')

    const link = container.querySelector('a')
    expect(link).not.toBeNull()
    expect(link?.getAttribute('href')).toBe('https://github.com')
    expect(link?.getAttribute('target')).toBe('_blank')
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer')
  })
})
