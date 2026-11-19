import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from './api'

afterEach(() => vi.unstubAllGlobals())

function failWith(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

async function messageOf(promise: Promise<unknown>): Promise<string> {
  const error = await promise.catch((e: unknown) => e)
  expect(error).toBeInstanceOf(ApiError)
  return (error as ApiError).message
}

describe('api error messages', () => {
  it('uses a string detail as is', async () => {
    failWith(404, { detail: 'application not found' })

    expect(await messageOf(api('/applications/9'))).toBe('application not found')
  })

  it('strips the Pydantic "Value error" prefix and the body location', async () => {
    failWith(422, {
      detail: [
        { loc: ['body'], msg: 'Value error, posting_url must be an http or https URL' },
      ],
    })

    expect(await messageOf(api('/applications/9'))).toBe('posting_url must be an http or https URL')
  })

  it('names the field for a field-level validation error', async () => {
    failWith(422, { detail: [{ loc: ['body', 'company'], msg: 'String should have at least 1 character' }] })

    expect(await messageOf(api('/applications/9'))).toBe(
      'company: String should have at least 1 character',
    )
  })

  it('falls back to the status when the body has no detail', async () => {
    failWith(500, null)

    expect(await messageOf(api('/applications'))).toBe('Request failed (500)')
  })
})
