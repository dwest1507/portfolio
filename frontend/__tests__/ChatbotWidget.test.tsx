import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UIMessage } from '@ai-sdk/react'
import ChatbotWidget from '@/components/chatbot/ChatbotWidget'

const mockUseChat = vi.fn()

vi.mock('@ai-sdk/react', () => ({
  useChat: (options: unknown) => mockUseChat(options),
}))

vi.mock('ai', () => ({
  TextStreamChatTransport: vi.fn(),
}))

function makeMessage(id: string, role: 'user' | 'assistant', text: string): UIMessage {
  return { id, role, parts: [{ type: 'text', text }] } as UIMessage
}

interface ChatState {
  messages?: UIMessage[]
  status?: 'ready' | 'submitted' | 'streaming' | 'error'
  error?: Error
  sendMessage?: ReturnType<typeof vi.fn>
  stop?: ReturnType<typeof vi.fn>
}

function setChatState(state: ChatState = {}) {
  const sendMessage = state.sendMessage ?? vi.fn()
  mockUseChat.mockReturnValue({
    messages: state.messages ?? [],
    sendMessage,
    status: state.status ?? 'ready',
    error: state.error,
    stop: state.stop ?? vi.fn(),
  })
  return { sendMessage }
}

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Open chat assistant' }))
}

describe('ChatbotWidget', () => {
  beforeEach(() => {
    mockUseChat.mockReset()
    sessionStorage.clear()
    // Skip the delayed onboarding tooltip in tests
    sessionStorage.setItem('chatTooltipSeen', '1')
  })

  it('starts closed and opens when the trigger button is clicked', async () => {
    setChatState()
    const user = userEvent.setup()
    render(<ChatbotWidget />)

    const panel = screen.getByRole('dialog', { hidden: true })
    expect(panel).toHaveAttribute('aria-hidden', 'true')

    await openPanel(user)
    expect(panel).toHaveAttribute('aria-hidden', 'false')
    expect(screen.getByRole('button', { name: 'Close chat assistant' })).toHaveAttribute(
      'aria-expanded',
      'true'
    )
  })

  it('closes again when the trigger button is clicked twice', async () => {
    setChatState()
    const user = userEvent.setup()
    render(<ChatbotWidget />)

    await openPanel(user)
    await user.click(screen.getByRole('button', { name: 'Close chat assistant' }))
    expect(screen.getByRole('dialog', { hidden: true })).toHaveAttribute('aria-hidden', 'true')
  })

  it('shows the welcome message', async () => {
    setChatState()
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    expect(
      screen.getByText(
        "Hi! I'm David's AI assistant. Ask me anything about his experience, skills, or projects."
      )
    ).toBeInTheDocument()
  })

  it('renders the conversation messages', async () => {
    setChatState({
      messages: [
        makeMessage('1', 'user', 'What are your skills?'),
        makeMessage('2', 'assistant', 'David works with Python and TypeScript.'),
      ],
    })
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    expect(screen.getByText('What are your skills?')).toBeInTheDocument()
    expect(screen.getByText('David works with Python and TypeScript.')).toBeInTheDocument()
  })

  it('sends the trimmed input on submit and clears the field', async () => {
    const { sendMessage } = setChatState()
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    const input = screen.getByRole('textbox')
    await user.type(input, '  Tell me about David  ')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(sendMessage).toHaveBeenCalledWith({ text: 'Tell me about David' })
    expect(input).toHaveValue('')
  })

  it('blocks a second message sent within the 3 second debounce window', async () => {
    const { sendMessage } = setChatState()
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    const input = screen.getByRole('textbox')
    await user.type(input, 'First message{Enter}')
    expect(sendMessage).toHaveBeenCalledTimes(1)

    // Input is disabled while debounced, so a second send is impossible
    expect(input).toBeDisabled()
    expect(input).toHaveAttribute('placeholder', 'Please wait a moment...')
  })

  it('shows the typing indicator while waiting for the first token', async () => {
    setChatState({
      messages: [makeMessage('1', 'user', 'Hello')],
      status: 'submitted',
    })
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    expect(screen.getByLabelText('Assistant is thinking')).toBeInTheDocument()
  })

  it('shows a stop button while a response is streaming', async () => {
    const stop = vi.fn()
    setChatState({
      messages: [makeMessage('1', 'user', 'Hello')],
      status: 'streaming',
      stop,
    })
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    await user.click(screen.getByRole('button', { name: 'Stop generating' }))
    expect(stop).toHaveBeenCalled()
  })

  it('shows a friendly error message on failure', async () => {
    setChatState({ status: 'error', error: new Error('boom') })
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    expect(
      screen.getByText("Sorry, I'm having trouble responding right now. Please try again.")
    ).toBeInTheDocument()
    // Raw error details never leak into the UI
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument()
  })

  it('disables input and shows a notice once the 50 message limit is reached', async () => {
    setChatState({
      messages: Array.from({ length: 50 }, (_, i) => makeMessage(`${i}`, 'user', `Message ${i}`)),
    })
    const user = userEvent.setup()
    render(<ChatbotWidget />)
    await openPanel(user)

    expect(screen.getByText('— session limit reached —')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})
