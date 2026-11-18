export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI sends `detail` as a string for errors it raises and as a list for validation errors.
function messageFrom(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const first = detail[0] as { loc?: unknown[]; msg?: string } | undefined
    if (first?.msg) {
      // Errors raised by our own validators arrive as "Value error, <message>" located at "body".
      const msg = first.msg.replace(/^Value error, /, '')
      const field = first.loc?.at(-1)
      return field && field !== 'body' ? `${String(field)}: ${msg}` : msg
    }
  }
  return fallback
}

export async function api<T>(path: string, init?: { method: string; body: unknown }): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    init && {
      method: init.method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(init.body),
    },
  )
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, messageFrom(body, `Request failed (${response.status})`))
  }
  return body as T
}
