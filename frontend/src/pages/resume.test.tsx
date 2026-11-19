import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mockApi, renderAt } from '@/test-utils'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

beforeEach(() => {
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const RESUME = '# Jordan Avery\nLead Software Engineer'

function sampleResume(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    content_markdown: RESUME,
    status: 'approved',
    created_at: '2026-11-12T12:00:00Z',
    updated_at: '2026-11-12T12:00:00Z',
    reviewed_at: null,
    ...overrides,
  }
}

const NOT_FOUND = { status: 404, body: { detail: 'resume not found' } }

function editor() {
  return screen.getByLabelText('Resume in Markdown') as HTMLTextAreaElement
}

function saveButton() {
  return screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement
}

describe('base resume page', () => {
  it('shows the title, the Save button and the labeled monospace editor', async () => {
    mockApi(() => NOT_FOUND)
    renderAt('/resume')

    expect(await screen.findByRole('heading', { name: 'Base resume' })).toBeTruthy()
    expect(screen.getByText('Every tailored resume is written from this document.')).toBeTruthy()
    expect(saveButton()).toBeTruthy()
    expect(editor().tagName).toBe('TEXTAREA')
    expect(editor().className).toContain('font-mono')
  })

  it('shows the four points in the How this is used panel', async () => {
    mockApi(() => ({ body: sampleResume() }))
    renderAt('/resume')

    expect(await screen.findByText('How this is used')).toBeTruthy()
    expect(screen.getByText(/Tailoring only rephrases, reorders and emphasizes/)).toBeTruthy()
    expect(screen.getByText(/Every tailored draft is checked against this text/)).toBeTruthy()
    expect(screen.getByText(/If a posting shows a missing keyword you really have/)).toBeTruthy()
    expect(screen.getByText(/Include everything you can honestly claim/)).toBeTruthy()
  })

  it('loads the saved resume into the editor and shows when it was saved', async () => {
    mockApi(() => ({ body: sampleResume() }))
    renderAt('/resume')

    await waitFor(() => expect(editor().value).toBe(RESUME))
    expect(screen.getByText(/^Last saved Nov 12,/)).toBeTruthy()
  })
})

describe('empty state', () => {
  it('shows an empty editor, no Last saved time and the same panel when there is no resume', async () => {
    mockApi(() => NOT_FOUND)
    renderAt('/resume')

    expect(await screen.findByText('How this is used')).toBeTruthy()
    expect(editor().value).toBe('')
    expect(screen.queryByText(/Last saved/)).toBeNull()
    // A missing resume is a normal state, not an error.
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('does not retry the 404', async () => {
    const calls = mockApi(() => NOT_FOUND)
    renderAt('/resume')

    await screen.findByText('How this is used')
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(calls.filter((c) => c.method === 'GET')).toHaveLength(1)
  })
})

describe('saving', () => {
  it('sends the text with PUT /resume, then shows the saved time and a success toast', async () => {
    const calls = mockApi(({ method, body }) => {
      if (method === 'PUT') {
        return {
          body: sampleResume({
            content_markdown: (body as { content_markdown: string }).content_markdown,
            updated_at: '2026-11-13T12:00:00Z',
          }),
        }
      }
      return NOT_FOUND
    })
    renderAt('/resume')

    await screen.findByText('How this is used')
    fireEvent.change(editor(), { target: { value: RESUME } })
    fireEvent.click(saveButton())

    expect(await screen.findByText(/^Last saved Nov 13,/)).toBeTruthy()
    expect(calls.find((c) => c.method === 'PUT')).toEqual({
      method: 'PUT',
      path: '/api/resume',
      body: { content_markdown: RESUME },
    })
    expect(editor().value).toBe(RESUME)
    expect(toast.success).toHaveBeenCalledWith('Resume saved')
  })

  it('replaces an existing resume with the edited text', async () => {
    let current = sampleResume()
    const calls = mockApi(({ method, body }) => {
      if (method === 'PUT') {
        current = sampleResume({
          content_markdown: (body as { content_markdown: string }).content_markdown,
          updated_at: '2026-11-14T12:00:00Z',
        })
      }
      return { body: current }
    })
    renderAt('/resume')

    await waitFor(() => expect(editor().value).toBe(RESUME))
    fireEvent.change(editor(), { target: { value: `${RESUME}\n\n## Skills` } })
    fireEvent.click(saveButton())

    expect(await screen.findByText(/^Last saved Nov 14,/)).toBeTruthy()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      content_markdown: `${RESUME}\n\n## Skills`,
    })
  })

  it('a failed save toasts the API message and keeps the text', async () => {
    mockApi(({ method }) =>
      method === 'PUT' ? { status: 500, body: { detail: 'database is down' } } : NOT_FOUND,
    )
    renderAt('/resume')

    await screen.findByText('How this is used')
    fireEvent.change(editor(), { target: { value: 'keep me' } })
    fireEvent.click(saveButton())

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('database is down'))
    expect(editor().value).toBe('keep me')
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('does not save a blank resume', async () => {
    const calls = mockApi(() => NOT_FOUND)
    renderAt('/resume')

    await screen.findByText('How this is used')
    expect(saveButton().disabled).toBe(true)
    fireEvent.change(editor(), { target: { value: '   \n' } })
    expect(saveButton().disabled).toBe(true)
    fireEvent.click(saveButton())

    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(calls.filter((c) => c.method === 'PUT')).toEqual([])
  })

  it('enables Save once there is text', async () => {
    mockApi(() => NOT_FOUND)
    renderAt('/resume')

    await screen.findByText('How this is used')
    fireEvent.change(editor(), { target: { value: 'something' } })

    expect(saveButton().disabled).toBe(false)
  })
})
