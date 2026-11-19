import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  mockApi,
  renderAt,
  sampleAnalysis,
  sampleApplication,
  sampleEvent,
  type ApiHandler,
} from '@/test-utils'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

// Radix menus measure and observe elements; jsdom has neither.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/**
 * A detail page whose analysis changes as the user acts: Analyze creates a draft, and approve
 * and reject return the decided analysis, which the next GET then returns.
 */
function analysisApi(initial: Record<string, unknown> | null) {
  let current = initial
  return mockApi(({ method, path }) => {
    if (path === '/api/applications/1') return { body: sampleApplication() }
    if (path === '/api/applications/1/timeline') return { body: [sampleEvent()] }
    if (path === '/api/applications/1/analysis' && method === 'GET') return { body: current }
    if (path === '/api/applications/1/analysis' && method === 'POST') {
      current = sampleAnalysis({ id: 9, status: 'draft' })
      return { status: 201, body: current }
    }
    if (path === '/api/analyses/5/approve') {
      current = { ...current, status: 'approved', reviewed_at: '2026-11-17T09:00:00Z' }
      return { body: current }
    }
    if (path === '/api/analyses/5/reject') {
      current = { ...current, status: 'rejected', reviewed_at: '2026-11-17T09:00:00Z' }
      return { body: current }
    }
    return { status: 404, body: { detail: 'not found' } }
  })
}

/** A detail page where every call is answered by `answer`, falling back to the basics. */
function apiWith(analysis: Record<string, unknown> | null, answer: ApiHandler) {
  return mockApi((req) => {
    const custom = answer(req)
    if (custom.status !== 404) return custom
    if (req.path === '/api/applications/1/analysis') return { body: analysis }
    if (req.path.endsWith('/timeline')) return { body: [sampleEvent()] }
    if (req.path.endsWith('/tailored-resumes')) return { body: [] }
    // These tests are not about coverage: no base resume, and nothing to measure.
    if (req.path === '/api/resume' || req.path.endsWith('/coverage')) {
      return { status: 404, body: { detail: 'not found' } }
    }
    return { body: sampleApplication() }
  })
}
const passThrough: ApiHandler = () => ({ status: 404, body: null })

/** The Posting analysis card, once the page has loaded. */
async function openCard() {
  return within(await screen.findByRole('region', { name: 'Posting analysis' }))
}

function buttonNamed(name: string): HTMLButtonElement {
  return screen.getByRole('button', { name }) as HTMLButtonElement
}

describe('empty state', () => {
  it('says there is no analysis and offers Analyze', async () => {
    analysisApi(null)
    renderAt('/applications/1')

    const card = await openCard()
    expect(await card.findByText('No analysis yet')).toBeTruthy()
    expect(card.getByRole('button', { name: 'Analyze' })).toBeTruthy()
    expect(card.queryByRole('button', { name: /approve|reject|analyze again/i })).toBeNull()
  })

  it('sits beside the Job posting card', async () => {
    analysisApi(null)
    renderAt('/applications/1')

    const posting = await screen.findByRole('region', { name: 'Job posting' })
    const analysis = screen.getByRole('region', { name: 'Posting analysis' })
    expect(posting.parentElement).toBe(analysis.parentElement)
  })

  it('Analyze posts to the API and then shows the draft', async () => {
    const calls = analysisApi(null)
    renderAt('/applications/1')

    fireEvent.click(await (await openCard()).findByRole('button', { name: 'Analyze' }))

    expect(await (await openCard()).findByText('Draft')).toBeTruthy()
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual([
      '/api/applications/1/analysis',
    ])
  })
})

describe('draft state', () => {
  it('shows the badge, the lists, the keywords and the three buttons', async () => {
    analysisApi(sampleAnalysis({ id: 5 }))
    renderAt('/applications/1')

    const card = await openCard()
    expect(await card.findByText('Draft')).toBeTruthy()
    expect(card.getByText('Prompt v1 · Generated Nov 16')).toBeTruthy()
    expect(card.getByText('Must have')).toBeTruthy()
    expect(card.getByText('Nice to have')).toBeTruthy()
    for (const keyword of ['ruby on rails', 'postgresql', 'ci/cd']) {
      expect(card.getByText(keyword)).toBeTruthy()
    }
    for (const name of ['Analyze again', 'Reject', 'Approve']) {
      expect(card.getByRole('button', { name })).toBeTruthy()
    }
  })

  it('keeps must-have and nice-to-have requirements in their own lists', async () => {
    analysisApi(sampleAnalysis({ id: 5 }))
    renderAt('/applications/1')
    await screen.findByText('Draft')

    const must = screen.getByRole('list', { name: 'Must have' })
    const nice = screen.getByRole('list', { name: 'Nice to have' })
    expect(within(must).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Ruby on Rails services in production',
      'PostgreSQL',
    ])
    expect(within(nice).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['CI/CD'])
  })

  it('Approve posts the decision and the card changes in place', async () => {
    const calls = analysisApi(sampleAnalysis({ id: 5 }))
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    const card = await openCard()
    expect(await card.findByText('Approved')).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST')?.path).toBe('/api/analyses/5/approve')
    expect(card.queryByRole('button', { name: /approve|reject/i })).toBeNull()
    expect(card.getByRole('button', { name: 'Analyze again' })).toBeTruthy()
  })

  it('Reject posts the decision and the card changes in place', async () => {
    const calls = analysisApi(sampleAnalysis({ id: 5 }))
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))

    const card = await openCard()
    expect(await card.findByText('Rejected')).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST')?.path).toBe('/api/analyses/5/reject')
    expect(card.queryByRole('button', { name: /approve|reject/i })).toBeNull()
  })

  it('Analyze again posts a new analysis and shows the new draft', async () => {
    const calls = analysisApi(sampleAnalysis({ id: 5, status: 'rejected' }))
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Analyze again' }))

    expect(await (await openCard()).findByText('Draft')).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST')?.path).toBe('/api/applications/1/analysis')
  })
})

describe('approved and rejected states', () => {
  it.each([
    ['approved', 'Approved'],
    ['rejected', 'Rejected'],
  ])('%s shows its badge and only Analyze again', async (status, badge) => {
    analysisApi(sampleAnalysis({ id: 5, status, reviewed_at: '2026-11-17T09:00:00Z' }))
    renderAt('/applications/1')

    const card = await openCard()
    expect(await card.findByText(badge)).toBeTruthy()
    expect(card.getByText('Prompt v1 · Generated Nov 16')).toBeTruthy()
    expect(card.getAllByRole('button').map((b) => b.textContent)).toEqual(['Analyze again'])
    // What was extracted stays visible after the decision.
    expect(card.getByText('PostgreSQL')).toBeTruthy()
  })
})

describe('while the call runs', () => {
  /** Makes the analysis POST wait until the test releases it. Other calls are answered. */
  function holdPost() {
    let release: (response: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => (release = resolve))
    const answer = globalThis.fetch
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === 'POST' ? pending : answer(input, init),
      ),
    )
    return (analysis: Record<string, unknown>) =>
      release(
        new Response(JSON.stringify(analysis), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
  }

  async function expectEveryButtonDisabled() {
    await waitFor(async () => expect((await openCard()).getByText('Analyzing…')).toBeTruthy())
    const buttons = (await openCard()).getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
    for (const button of buttons) expect((button as HTMLButtonElement).disabled).toBe(true)
  }

  it('disables every button and shows a loading label until Analyze again finishes', async () => {
    analysisApi(sampleAnalysis({ id: 5 }))
    const finish = holdPost()
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Analyze again' }))
    await expectEveryButtonDisabled()

    finish(sampleAnalysis({ id: 9 }))
    await waitFor(async () => expect((await openCard()).queryByText('Analyzing…')).toBeNull())
    expect(buttonNamed('Analyze again').disabled).toBe(false)
  })

  it('disables the first Analyze button too', async () => {
    analysisApi(null)
    const finish = holdPost()
    renderAt('/applications/1')

    fireEvent.click(await (await openCard()).findByRole('button', { name: 'Analyze' }))
    await expectEveryButtonDisabled()

    finish(sampleAnalysis({ id: 9 }))
    await waitFor(async () => expect((await openCard()).queryByText('Analyzing…')).toBeNull())
  })
})

describe('failures', () => {
  it('toasts the API message when the analysis fails and keeps the card as it was', async () => {
    apiWith(sampleAnalysis({ id: 5 }), ({ method, path }) =>
      method === 'POST' && path === '/api/applications/1/analysis'
        ? { status: 502, body: { detail: 'The analysis failed. Try again.' } }
        : passThrough({ method, path, body: null }),
    )
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Analyze again' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('The analysis failed. Try again.'),
    )
    expect((await openCard()).getByText('Draft')).toBeTruthy()
    expect(buttonNamed('Analyze again').disabled).toBe(false)
  })

  it('toasts when another analysis is already running (409)', async () => {
    apiWith(null, ({ method, path }) =>
      method === 'POST' && path === '/api/applications/1/analysis'
        ? { status: 409, body: { detail: 'An analysis is already running.' } }
        : passThrough({ method, path, body: null }),
    )
    renderAt('/applications/1')

    fireEvent.click(await (await openCard()).findByRole('button', { name: 'Analyze' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('An analysis is already running.'),
    )
    expect((await openCard()).getByText('No analysis yet')).toBeTruthy()
  })

  it('toasts when a decision fails and leaves the draft in place', async () => {
    apiWith(sampleAnalysis({ id: 5 }), ({ method, path }) =>
      method === 'POST' && path === '/api/analyses/5/approve'
        ? { status: 409, body: { detail: 'analysis is already decided' } }
        : passThrough({ method, path, body: null }),
    )
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('analysis is already decided'))
    expect((await openCard()).getByText('Draft')).toBeTruthy()
  })
})
