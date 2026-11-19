import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  detailHandler,
  mockApi,
  renderAt,
  sampleApplication,
  sampleEvent,
  sampleList,
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

const applied = sampleApplication({
  id: 2,
  company: 'Tallgrass Payments',
  stage: 'applied',
  allowed_next_stages: ['screening', 'interviewing', 'rejected', 'withdrawn'],
  last_activity_at: '2026-11-13T12:00:00Z',
})
const stale = sampleApplication({
  id: 3,
  company: 'Fernhill Logistics',
  stage: 'applied',
  last_activity_at: '2026-10-30T12:00:00Z',
  is_stale: true,
  idle_days: 18,
})
const saved = sampleApplication({ last_activity_at: '2026-11-14T12:00:00Z' })

function openMenu() {
  fireEvent.keyDown(screen.getByRole('button', { name: /change stage/i }), { key: 'Enter' })
}

describe('stage filter pills', () => {
  it('shows All and one pill per stage with the counts from the API', async () => {
    mockApi(() => ({ body: sampleList([saved, applied, stale]) }))
    renderAt('/')

    expect(await screen.findByRole('button', { name: 'All 3' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Saved 1' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Applied 2' })).toBeTruthy()
    for (const name of ['Screening', 'Interviewing', 'Offer', 'Accepted', 'Rejected', 'Withdrawn']) {
      expect(screen.getByRole('button', { name: `${name} 0` })).toBeTruthy()
    }
    expect(screen.getByRole('button', { name: 'All 3' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('clicking a pill asks the API for that stage and keeps the counts', async () => {
    const calls = mockApi(({ path }) => {
      const everything = sampleList([saved, applied, stale])
      if (path.includes('stage=applied')) return { body: { ...everything, items: [applied, stale] } }
      return { body: everything }
    })
    renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: 'Applied 2' }))

    await waitFor(() => expect(screen.queryByRole('link', { name: 'Northwind Freight' })).toBeNull())
    expect(calls.some((c) => c.path === '/api/applications?stage=applied')).toBe(true)
    expect(screen.getByRole('link', { name: 'Tallgrass Payments' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Applied 2' }).getAttribute('aria-pressed')).toBe(
      'true',
    )
    // The counts still cover every application.
    expect(screen.getByRole('button', { name: 'All 3' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Saved 1' })).toBeTruthy()
    expect(screen.getByText('3 applications')).toBeTruthy()
  })

  it('clicking All clears the filter', async () => {
    const calls = mockApi(() => ({ body: sampleList([saved, applied]) }))
    const { router } = renderAt('/?stage=applied')

    fireEvent.click(await screen.findByRole('button', { name: 'All 2' }))

    await waitFor(() => expect(router.state.location.search).toBe(''))
    expect(calls.at(-1)?.path).toBe('/api/applications')
  })

  it('reads the stage from the URL so Back from a detail page keeps the filter', async () => {
    const calls = mockApi(() => ({ body: sampleList([applied]) }))
    renderAt('/?stage=applied')

    await screen.findByRole('link', { name: 'Tallgrass Payments' })
    expect(calls[0].path).toBe('/api/applications?stage=applied')
    expect(screen.getByRole('button', { name: 'Applied 1' }).getAttribute('aria-pressed')).toBe(
      'true',
    )
  })
})

describe('last activity and stale rows', () => {
  it('shows a Last activity column instead of Added', async () => {
    mockApi(() => ({ body: sampleList([saved]) }))
    renderAt('/')

    await screen.findByRole('link', { name: 'Northwind Freight' })
    expect(screen.getByRole('columnheader', { name: 'Last activity' })).toBeTruthy()
    expect(screen.queryByRole('columnheader', { name: 'Added' })).toBeNull()
    expect(within(screen.getByRole('link', { name: 'Northwind Freight' }).closest('tr')!).getByText('Nov 14')).toBeTruthy()
  })

  it('tags stale rows with the idle days and leaves other rows alone', async () => {
    mockApi(() => ({ body: sampleList([saved, stale]) }))
    renderAt('/')

    const staleRow = (await screen.findByRole('link', { name: 'Fernhill Logistics' })).closest('tr')!
    expect(within(staleRow).getByText('Stale, 18 days')).toBeTruthy()
    expect(within(staleRow).getByText('Oct 30')).toBeTruthy()
    const freshRow = screen.getByRole('link', { name: 'Northwind Freight' }).closest('tr')!
    expect(within(freshRow).queryByText(/Stale/)).toBeNull()
  })

  it('shows a notice above the table when any application is stale', async () => {
    mockApi(() => ({ body: sampleList([saved, stale], { stale_count: 2 }) }))
    renderAt('/')

    expect(await screen.findByText(/2 applications have had no recent activity/)).toBeTruthy()
  })

  it('uses the singular for one stale application', async () => {
    mockApi(() => ({ body: sampleList([saved, stale]) }))
    renderAt('/')

    expect(await screen.findByText(/1 application has had no recent activity/)).toBeTruthy()
  })

  it('shows no notice when nothing is stale', async () => {
    mockApi(() => ({ body: sampleList([saved, applied]) }))
    renderAt('/')

    await screen.findByRole('link', { name: 'Northwind Freight' })
    expect(screen.queryByText(/no recent activity/)).toBeNull()
  })

  it('keeps the notice while a filter hides the stale rows', async () => {
    mockApi(() => ({ body: sampleList([saved, stale], { items: [saved] }) }))
    renderAt('/?stage=saved')

    expect(await screen.findByText(/1 application has had no recent activity/)).toBeTruthy()
  })
})

describe('change stage control', () => {
  it('lists only the stages the API allows', async () => {
    mockApi(detailHandler(applied))
    renderAt('/applications/2')

    await screen.findByRole('heading', { name: 'Tallgrass Payments' })
    openMenu()

    const items = (await screen.findAllByRole('menuitem')).map((i) => i.textContent)
    expect(items).toEqual(['Screening', 'Interviewing', 'Rejected', 'Withdrawn'])
  })

  it('shows what the API says even when it is not the usual table', async () => {
    mockApi(detailHandler(sampleApplication({ allowed_next_stages: ['offer'] })))
    renderAt('/applications/1')

    await screen.findByRole('heading', { name: 'Northwind Freight' })
    openMenu()

    expect((await screen.findAllByRole('menuitem')).map((i) => i.textContent)).toEqual(['Offer'])
  })

  it('choosing a stage posts it, then shows the new stage and timeline entry', async () => {
    let current = sampleApplication()
    let events = [sampleEvent()]
    const calls = mockApi(({ method, path }) => {
      if (method === 'POST' && path === '/api/applications/1/stage') {
        current = sampleApplication({ stage: 'withdrawn', allowed_next_stages: [] })
        events = [sampleEvent({ id: 2, from_stage: 'saved', to_stage: 'withdrawn' }), ...events]
        return { body: current }
      }
      return detailHandler(current, events)({ method, path, body: undefined })
    })
    renderAt('/applications/1')

    await screen.findByRole('heading', { name: 'Northwind Freight' })
    openMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Withdrawn' }))

    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')).toEqual({
        method: 'POST',
        path: '/api/applications/1/stage',
        body: { to_stage: 'withdrawn' },
      }),
    )
    expect(await screen.findByText('Saved → Withdrawn')).toBeTruthy()
    expect(toast.success).toHaveBeenCalled()
    // Terminal now: nothing left to choose.
    await waitFor(() =>
      expect((screen.getByRole('button', { name: /change stage/i }) as HTMLButtonElement).disabled).toBe(
        true,
      ),
    )
  })

  it('is disabled when no stage is allowed', async () => {
    mockApi(detailHandler(sampleApplication({ stage: 'rejected', allowed_next_stages: [] })))
    renderAt('/applications/1')

    await screen.findByRole('heading', { name: 'Northwind Freight' })

    expect((screen.getByRole('button', { name: /change stage/i }) as HTMLButtonElement).disabled).toBe(
      true,
    )
  })

  it('toasts the API message when a move is refused', async () => {
    mockApi((req) =>
      req.method === 'POST'
        ? {
            status: 409,
            body: {
              detail: {
                message: 'cannot move from saved to withdrawn',
                allowed_next_stages: [],
              },
            },
          }
        : detailHandler()(req),
    )
    renderAt('/applications/1')

    await screen.findByRole('heading', { name: 'Northwind Freight' })
    openMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Withdrawn' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('cannot move from saved to withdrawn'),
    )
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('reloads the application after a refused move so the options are current', async () => {
    // The page opened while the application was Saved. Meanwhile it moved to Applied elsewhere.
    let current = sampleApplication()
    const calls = mockApi(({ method, path, body }) => {
      if (method === 'POST') {
        current = applied
        return {
          status: 409,
          body: { detail: { message: 'cannot move from applied to applied', allowed_next_stages: [] } },
        }
      }
      return detailHandler(current)({ method, path, body })
    })
    renderAt('/applications/1')

    await screen.findByRole('heading', { name: 'Northwind Freight' })
    openMenu()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Withdrawn' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    await waitFor(() =>
      expect(calls.filter((c) => c.method === 'GET' && c.path === '/api/applications/1')).toHaveLength(2),
    )
    openMenu()
    const items = (await screen.findAllByRole('menuitem')).map((i) => i.textContent)
    expect(items).toEqual(['Screening', 'Interviewing', 'Rejected', 'Withdrawn'])
  })
})

describe('timeline', () => {
  const events = [
    sampleEvent({ id: 3, type: 'note', from_stage: null, to_stage: null, note: 'Phone screen booked' }),
    sampleEvent({ id: 2, from_stage: 'saved', to_stage: 'applied', created_at: '2026-11-13T09:00:00Z' }),
    sampleEvent({ id: 1 }),
  ]

  it('lists events in the order the API sends them, newest first', async () => {
    mockApi(detailHandler(sampleApplication(), events))
    renderAt('/applications/1')

    const section = (await screen.findByRole('heading', { name: 'Timeline' })).closest('section')!
    const items = await within(section).findAllByRole('listitem')
    const entries = items.map((li) => li.textContent ?? '')
    expect(entries).toHaveLength(3)
    expect(entries[0]).toContain('Phone screen booked')
    expect(entries[1]).toContain('Saved → Applied')
    expect(entries[2]).toContain('Created in Saved')
  })

  it('shows the Add a note field and button', async () => {
    mockApi(detailHandler())
    renderAt('/applications/1')

    expect(await screen.findByLabelText('Add a note')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add note' })).toBeTruthy()
  })

  it('adding a note posts it, clears the field and shows it at the top', async () => {
    let timeline = [sampleEvent()]
    const calls = mockApi(({ method, path, body }) => {
      if (method === 'POST' && path === '/api/applications/1/notes') {
        const event = sampleEvent({
          id: 2,
          type: 'note',
          from_stage: null,
          to_stage: null,
          note: (body as { note: string }).note,
        })
        timeline = [event, ...timeline]
        return { status: 201, body: event }
      }
      return detailHandler(sampleApplication(), timeline)({ method, path, body })
    })
    renderAt('/applications/1')

    const field = (await screen.findByLabelText('Add a note')) as HTMLInputElement
    fireEvent.change(field, { target: { value: 'Phone screen booked for Thursday' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add note' }))

    expect(await screen.findByText('Phone screen booked for Thursday')).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST')).toEqual({
      method: 'POST',
      path: '/api/applications/1/notes',
      body: { note: 'Phone screen booked for Thursday' },
    })
    expect(field.value).toBe('')
  })

  it('does not post a blank note', async () => {
    const calls = mockApi(detailHandler())
    renderAt('/applications/1')

    const field = await screen.findByLabelText('Add a note')
    const button = screen.getByRole('button', { name: 'Add note' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.change(field, { target: { value: '   ' } })
    expect(button.disabled).toBe(true)
    fireEvent.click(button)

    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(calls.filter((c) => c.method === 'POST')).toEqual([])
  })

  it('a failed note toasts the error and keeps the text', async () => {
    mockApi((req) =>
      req.method === 'POST'
        ? { status: 500, body: { detail: 'database is down' } }
        : detailHandler()(req),
    )
    renderAt('/applications/1')

    const field = (await screen.findByLabelText('Add a note')) as HTMLInputElement
    fireEvent.change(field, { target: { value: 'keep me' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add note' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('database is down'))
    expect(field.value).toBe('keep me')
  })
})
