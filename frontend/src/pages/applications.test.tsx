import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { detailHandler, mockApi, renderAt, sampleApplication, sampleList } from '@/test-utils'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

beforeEach(() => {
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
})

// Vitest globals are off, so Testing Library does not clean up between tests on its own.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const second = sampleApplication({
  id: 2,
  company: 'Larkspur Health',
  role: 'Staff Engineer, Platform',
  source: 'referral',
  stage: 'interviewing',
  posting_url: null,
  created_at: '2026-11-15T12:00:00Z',
})

describe('applications list', () => {
  it('shows the total count and a row per application', async () => {
    mockApi(() => ({ body: sampleList([second, sampleApplication()]) }))
    renderAt('/')

    expect(await screen.findByText('2 applications')).toBeTruthy()
    const link = screen.getByRole('link', { name: 'Northwind Freight' })
    expect(link.getAttribute('href')).toBe('/applications/1')
    const row = link.closest('tr')!
    expect(within(row).getByText('Senior Backend Engineer')).toBeTruthy()
    expect(within(row).getByText('LinkedIn')).toBeTruthy()
    expect(within(row).getByText('Saved')).toBeTruthy()
    expect(within(row).getByText('Nov 12')).toBeTruthy() // last activity
    const otherRow = screen.getByRole('link', { name: 'Larkspur Health' }).closest('tr')!
    expect(within(otherRow).getByText('Interviewing')).toBeTruthy()
    expect(within(otherRow).getByText('Referral')).toBeTruthy()
  })

  it('shows an empty message when there are no applications', async () => {
    mockApi(() => ({ body: sampleList([]) }))
    renderAt('/')

    expect(await screen.findByText('0 applications')).toBeTruthy()
    expect(screen.getByText('No applications yet.')).toBeTruthy()
  })

  it('has no edit action', async () => {
    mockApi(() => ({ body: sampleList([sampleApplication()]) }))
    renderAt('/')

    await screen.findByText('1 application')
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull()
  })
})

describe('new application dialog', () => {
  it('opens with the five fields and the source options', async () => {
    mockApi(() => ({ body: sampleList([]) }))
    renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: /new application/i }))

    const dialog = await screen.findByRole('dialog')
    for (const label of ['Company', 'Role', 'Source', 'Posting URL', 'Posting text']) {
      expect(within(dialog).getByLabelText(new RegExp(label))).toBeTruthy()
    }
    const options = within(within(dialog).getByLabelText('Source') as HTMLElement)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(options).toEqual([
      'Select a source',
      'Referral',
      'LinkedIn',
      'Company site',
      'Recruiter',
      'Other',
    ])
  })

  it('saving closes the dialog, opens the detail page and toasts success', async () => {
    const created = sampleApplication({ id: 5 })
    const calls = mockApi(({ method, path }) => {
      if (method === 'POST') return { status: 201, body: created }
      if (path === '/api/applications/5') return { body: created }
      return { body: sampleList([]) }
    })
    const { router } = renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: /new application/i }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Company'), {
      target: { value: 'Northwind Freight' },
    })
    fireEvent.change(within(dialog).getByLabelText('Role'), {
      target: { value: 'Senior Backend Engineer' },
    })
    fireEvent.change(within(dialog).getByLabelText('Source'), { target: { value: 'linkedin' } })
    fireEvent.change(within(dialog).getByLabelText(/Posting URL/), {
      target: { value: 'https://northwind.example/careers/1' },
    })
    fireEvent.change(within(dialog).getByLabelText('Posting text'), {
      target: { value: 'Build services.' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save application' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/applications/5'))
    expect(calls.find((c) => c.method === 'POST')).toEqual({
      method: 'POST',
      path: '/api/applications',
      body: {
        company: 'Northwind Freight',
        role: 'Senior Backend Engineer',
        source: 'linkedin',
        posting_url: 'https://northwind.example/careers/1',
        posting_text: 'Build services.',
      },
    })
    expect(await screen.findByRole('heading', { name: 'Northwind Freight' })).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(toast.success).toHaveBeenCalled()
    // Saving runs no AI call: the only write is the one POST.
    expect(calls.filter((c) => c.method !== 'GET').map((c) => c.method)).toEqual(['POST'])
  })

  it('does not save until a source is chosen', async () => {
    const calls = mockApi(() => ({ body: sampleList([]) }))
    renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: /new application/i }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Company'), { target: { value: 'Acme' } })
    fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'Engineer' } })
    fireEvent.change(within(dialog).getByLabelText('Posting text'), { target: { value: 'Text' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save application' }))

    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(calls.filter((c) => c.method === 'POST')).toEqual([])
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('a failed save toasts the error and keeps the dialog open', async () => {
    mockApi(({ method }) =>
      method === 'POST'
        ? { status: 500, body: { detail: 'database is down' } }
        : { body: sampleList([]) },
    )
    const { router } = renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: /new application/i }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Company'), { target: { value: 'Acme' } })
    fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'Engineer' } })
    fireEvent.change(within(dialog).getByLabelText('Source'), { target: { value: 'other' } })
    fireEvent.change(within(dialog).getByLabelText('Posting text'), { target: { value: 'Text' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save application' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(router.state.location.pathname).toBe('/')
    expect(toast.success).not.toHaveBeenCalled()
  })
})

describe('application detail', () => {
  it('shows company, role, source, added date and stage badge', async () => {
    mockApi(detailHandler())
    renderAt('/applications/1')

    expect(await screen.findByRole('heading', { name: 'Northwind Freight' })).toBeTruthy()
    expect(screen.getByText('Saved')).toBeTruthy()
    expect(screen.getByText(/Senior Backend Engineer/)).toBeTruthy()
    expect(screen.getByText(/Source: LinkedIn/)).toBeTruthy()
    expect(screen.getByText(/Added Nov 12/)).toBeTruthy()
    expect(screen.getByText(/Build services that book/)).toBeTruthy()
  })

  it('shows an Open original link only when a posting URL exists', async () => {
    mockApi(detailHandler())
    renderAt('/applications/1')

    const link = await screen.findByRole('link', { name: 'Open original' })
    expect(link.getAttribute('href')).toBe('https://northwind.example/careers/1')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')

    cleanup()
    mockApi(detailHandler(sampleApplication({ posting_url: null })))
    renderAt('/applications/1')
    await screen.findByRole('heading', { name: 'Northwind Freight' })
    expect(screen.queryByRole('link', { name: 'Open original' })).toBeNull()
  })

  it('shows a not found message for an unknown application', async () => {
    mockApi(() => ({ status: 404, body: { detail: 'application not found' } }))
    renderAt('/applications/99')

    expect(await screen.findByText('Application not found.')).toBeTruthy()
  })

  it('Edit opens the dialog pre-filled and saving sends only the five editable fields', async () => {
    let current = sampleApplication()
    const calls = mockApi(({ method, path, body }) => {
      if (method === 'PATCH') {
        current = { ...current, ...(body as object) }
        return { body: current }
      }
      return detailHandler(current)({ method, path, body })
    })
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Edit application')).toBeTruthy()
    expect((within(dialog).getByLabelText('Company') as HTMLInputElement).value).toBe(
      'Northwind Freight',
    )
    expect((within(dialog).getByLabelText('Source') as HTMLSelectElement).value).toBe('linkedin')
    expect((within(dialog).getByLabelText(/Posting URL/) as HTMLInputElement).value).toBe(
      'https://northwind.example/careers/1',
    )

    fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'Staff Engineer' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const patch = calls.find((c) => c.method === 'PATCH')!
    expect(patch.path).toBe('/api/applications/1')
    expect(Object.keys(patch.body as object).sort()).toEqual([
      'company',
      'posting_text',
      'posting_url',
      'role',
      'source',
    ])
    expect((patch.body as { role: string }).role).toBe('Staff Engineer')
    expect(await screen.findByText(/Staff Engineer/)).toBeTruthy()
    expect(toast.success).toHaveBeenCalled()
  })

  it('a failed edit toasts a readable error and keeps the dialog open', async () => {
    mockApi((req) =>
      req.method === 'PATCH'
        ? {
            status: 422,
            body: {
              detail: [
                { loc: ['body'], msg: 'Value error, posting_url must be an http or https URL' },
              ],
            },
          }
        : detailHandler()(req),
    )
    renderAt('/applications/1')

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('posting_url must be an http or https URL'),
    )
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(toast.success).not.toHaveBeenCalled()
  })
})
