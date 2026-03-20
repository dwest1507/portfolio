import type { NextRequest } from 'next/server'

// UIMessage shape from @ai-sdk/react (simplified — we only need role + parts)
interface UIMessagePart {
  type: string
  text?: string
}

interface UIMessage {
  role: 'user' | 'assistant' | 'system'
  parts: UIMessagePart[]
}

function extractText(msg: UIMessage): string {
  return msg.parts
    .filter((p) => p.type === 'text')
    .map((p) => p.text ?? '')
    .join('')
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const messages: UIMessage[] = body.messages ?? []

  if (messages.length === 0) {
    return new Response('Message cannot be empty', { status: 400 })
  }

  const lastMessage = messages[messages.length - 1]
  const messageText = extractText(lastMessage)

  if (!messageText.trim()) {
    return new Response('Message cannot be empty', { status: 400 })
  }
  if (messageText.length > 500) {
    return new Response('Message too long (max 500 characters)', { status: 400 })
  }

  const history = messages.slice(0, -1).map((m) => ({
    role: m.role as 'user' | 'assistant',
    content: extractText(m),
  }))

  const backendUrl = process.env.CHAT_API_URL ?? 'http://localhost:8000'

  let backendResponse: Response
  try {
    backendResponse = await fetch(`${backendUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: messageText, history }),
    })
  } catch {
    return new Response('Service unavailable', { status: 502 })
  }

  if (!backendResponse.ok) {
    if (backendResponse.status === 429) {
      return new Response('Rate limit exceeded', { status: 429 })
    }
    if (backendResponse.status === 422 || backendResponse.status === 400) {
      return new Response('Invalid request', { status: 400 })
    }
    return new Response('Backend error', { status: 502 })
  }

  if (!backendResponse.body) {
    return new Response('Empty response from backend', { status: 502 })
  }

  // Transform the backend's AI SDK v1 data stream format (0:"token"\n)
  // into a plain text stream for TextStreamChatTransport.
  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder()
      const reader = backendResponse.body!.pipeThrough(new TextDecoderStream()).getReader()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += value
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (line.startsWith('0:')) {
              // AI SDK v1 text token: 0:"token"
              try {
                const token: string = JSON.parse(line.slice(2))
                controller.enqueue(encoder.encode(token))
              } catch {
                // skip malformed line
              }
            } else if (line.startsWith('3:')) {
              // AI SDK v1 error: 3:"message"
              controller.error(new Error('Generation failed'))
              return
            }
            // d: finish marker — just let the stream end naturally
          }
        }

        // flush any remaining buffer
        if (buffer.startsWith('0:')) {
          try {
            const token: string = JSON.parse(buffer.slice(2))
            controller.enqueue(encoder.encode(token))
          } catch {
            // skip
          }
        }
      } catch (err) {
        controller.error(err)
      } finally {
        controller.close()
        reader.releaseLock()
      }
    },
  })

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    },
  })
}
