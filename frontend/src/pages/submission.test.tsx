import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  detailHandler,
  mockApi,
  renderAt,
  sampleAnalysis,
  sampleApplication,
  sampleEvent,
  sampleList,
  sampleOption,
  sampleSteps,
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

const base = sampleOption({ id: 7, kind: 'base', date: '2026-11-12T12:00:00Z' })
const approvedTailored = sampleOption({
  id: 21,
  kind: 'tailored',
  status: 'approved',
  date: '2026-11-16T12:00:00Z',
})
const draftTailored = sampleOption({
  id: 22,
  kind: 'tailored',
  status: 'draft',
  date: '2026-11-17T12:00:00Z',
  submittable: false,
  reason: 'Approve this draft first',
})

const readyToApply = sampleApplication({
  steps: sampleSteps(
    ['done', 'Approved'],
    ['done', 'Approved'],
    ['current', 'Ready once you have submitted it'],
  ),
})

function section() {
  return screen.getByRole('region', { name: 'Mark as applied' })
}

async function openDetail(
  application: Record<string, unknown>,
  options: Record<string, unknown>[] = [],
) {
  const calls = mockApi(detailHandler(application, [sampleEvent()], null, options))
  renderAt('/applications/1')
  await screen.findByRole('heading', { name: application.company as string })
  return calls
}

describe('the three-step strip', () => {
  it('shows each step with its name, its status and one line of text from the API', async () => {
    await openDetail(sampleApplication())

    const steps = within(screen.getByRole('list', { name: 'Workflow steps' })).getAllByRole(
      'listitem',
    )
    expect(steps).toHaveLength(3)
    expect(steps[0].textContent).toContain('1. Posting analysis')
    expect(steps[0].textContent).toContain('Analyze the posting')
    expect(steps[1].textContent).toContain('2. Tailored resume')
    expect(steps[1].textContent).toContain('Locked until the analysis is approved')
    expect(steps[2].textContent).toContain('3. Mark as applied')
    expect(steps[2].textContent).toContain('Pick the resume you sent')
    expect(steps.map((s) => s.getAttribute('data-status'))).toEqual([
      'current',
      'locked',
      'available',
    ])
  })

  it('draws a check for a done step, a highlighted border for the current one and a dashed border for the rest', async () => {
    await openDetail(
      sampleApplication({
        steps: sampleSteps(['done', 'Approved'], ['current', 'Write a tailored draft'], ['skipped', 'x']),
      }),
    )

    const [done, current, skipped] = within(
      screen.getByRole('list', { name: 'Workflow steps' }),
    ).getAllByRole('listitem')
    expect(within(done).getByTestId('step-check')).toBeTruthy()
    expect(done.className).not.toContain('border-dashed')
    expect(within(current).queryByTestId('step-check')).toBeNull()
    expect(current.className).toContain('border-foreground')
    expect(current.className).not.toContain('border-dashed')
    expect(skipped.className).toContain('border-dashed')
  })

  it.each(['locked', 'available', 'skipped'])('uses a dashed border for a %s step', async (status) => {
    await openDetail(sampleApplication({ steps: sampleSteps([status, 'text']) }))

    const first = within(screen.getByRole('list', { name: 'Workflow steps' })).getAllByRole(
      'listitem',
    )[0]
    expect(first.className).toContain('border-dashed')
  })

  it('shows the statuses the API sends, not ones worked out from the stage', async () => {
    // A Saved application that the API says is already past step 1: the page does not argue.
    await openDetail(
      sampleApplication({ stage: 'saved', steps: sampleSteps(['skipped', 'Skipped']) }),
    )

    const first = within(screen.getByRole('list', { name: 'Workflow steps' })).getAllByRole(
      'listitem',
    )[0]
    expect(first.getAttribute('data-status')).toBe('skipped')
  })
})

describe('the Mark as applied section', () => {
  it('sits between the Tailored resume section and the Timeline', async () => {
    await openDetail(sampleApplication())

    const tailored = await screen.findByRole('region', { name: 'Tailored resume' })
    const timeline = screen.getByRole('heading', { name: 'Timeline' }).closest('section')!
    const follows = (a: Element, b: Element) =>
      Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

    expect(follows(tailored, section())).toBe(true)
    expect(follows(section(), timeline)).toBe(true)
  })

  describe('locked', () => {
    const locked = sampleApplication({
      steps: sampleSteps(['current', 'x'], ['locked', 'x'], ['locked', 'Locked until you save a base resume']),
    })

    it('links to the Resume page and offers nothing to choose', async () => {
      await openDetail(locked)

      const mark = within(section())
      expect(mark.getByRole('link', { name: /resume page/i }).getAttribute('href')).toBe('/resume')
      expect(mark.queryByRole('radio')).toBeNull()
      expect(mark.queryByRole('button', { name: 'Mark as applied' })).toBeNull()
    })

    it('does not ask for the resume options', async () => {
      const calls = await openDetail(locked)

      expect(calls.some((c) => c.path.endsWith('/submittable-resumes'))).toBe(false)
    })
  })

  describe('open', () => {
    it('asks which resume was sent and lists the API options, each with its date', async () => {
      await openDetail(readyToApply, [approvedTailored, base])

      const mark = within(section())
      expect(await mark.findByText('Which resume did you send?')).toBeTruthy()
      const radios = mark.getAllByRole('radio')
      expect(radios).toHaveLength(2)
      expect(mark.getByText(/Tailored resume/).textContent).toContain('Tailored resume')
      expect(mark.getByText(/Approved Nov 16/)).toBeTruthy()
      expect(mark.getByText(/Last saved Nov 12/)).toBeTruthy()
      expect(mark.getByText(/does not submit anything for you/)).toBeTruthy()
    })

    it('selects nothing at first, so the button waits for a choice', async () => {
      await openDetail(readyToApply, [approvedTailored, base])

      const mark = within(section())
      await mark.findAllByRole('radio')
      expect(mark.getAllByRole('radio').every((r) => r.getAttribute('aria-checked') === 'false')).toBe(true)
      expect((mark.getByRole('button', { name: 'Mark as applied' }) as HTMLButtonElement).disabled).toBe(true)
    })

    it('lists an option that cannot be sent, disabled, with the reason from the API', async () => {
      await openDetail(readyToApply, [draftTailored, approvedTailored, base])

      const mark = within(section())
      const radios = await mark.findAllByRole('radio')
      expect(radios).toHaveLength(3)
      expect((radios[0] as HTMLButtonElement).disabled).toBe(true)
      expect((radios[1] as HTMLButtonElement).disabled).toBe(false)
      expect(mark.getByText('Approve this draft first')).toBeTruthy()
    })

    it('trusts the API: a base resume it says cannot be sent is disabled too', async () => {
      await openDetail(readyToApply, [sampleOption({ submittable: false, reason: 'Not now' })])

      const radio = await within(section()).findByRole('radio')

      expect((radio as HTMLButtonElement).disabled).toBe(true)
      expect(within(section()).getByText('Not now')).toBeTruthy()
    })

    it('shows no keyword coverage beside the options', async () => {
      await openDetail(readyToApply, [approvedTailored, base])

      await within(section()).findAllByRole('radio')
      expect(within(section()).queryByText(/coverage/i)).toBeNull()
    })

    it('makes the button primary when step 3 is current', async () => {
      await openDetail(readyToApply, [approvedTailored, base])

      const button = await within(section()).findByRole('button', { name: 'Mark as applied' })

      expect(button.getAttribute('data-variant')).toBe('default')
    })

    it('makes the button secondary when step 3 is only available', async () => {
      await openDetail(sampleApplication(), [base])

      const button = await within(section()).findByRole('button', { name: 'Mark as applied' })

      expect(button.getAttribute('data-variant')).toBe('outline')
    })

    it('posts the base choice, then shows the application as applied', async () => {
      let current: Record<string, unknown> = readyToApply
      const calls = mockApi(({ method, path, body }) => {
        if (method === 'POST' && path === '/api/applications/1/apply') {
          current = sampleApplication({
            stage: 'applied',
            allowed_next_stages: ['screening', 'interviewing', 'rejected', 'withdrawn'],
            stage_change_hint: null,
            submitted_resume: { id: 30, kind: 'base', created_at: '2026-11-18T12:00:00Z' },
            applied_at: '2026-11-18T12:00:00Z',
            steps: sampleSteps(['done', 'Approved'], ['skipped', 'Skipped'], ['done', 'Resume sent']),
          })
          return { body: current }
        }
        return detailHandler(current, [sampleEvent()], null, [approvedTailored, base])({
          method,
          path,
          body,
        })
      })
      renderAt('/applications/1')
      await screen.findByRole('heading', { name: 'Northwind Freight' })

      const mark = within(section())
      const radios = await mark.findAllByRole('radio')
      fireEvent.click(radios[1]) // base
      fireEvent.click(mark.getByRole('button', { name: 'Mark as applied' }))

      await waitFor(() =>
        expect(calls.find((c) => c.method === 'POST')).toEqual({
          method: 'POST',
          path: '/api/applications/1/apply',
          body: { choice: 'base' },
        }),
      )
      expect(await within(section()).findByText(/Applied Nov 18 with the base resume/)).toBeTruthy()
      expect(within(section()).queryByRole('radio')).toBeNull()
      expect(toast.success).toHaveBeenCalled()
    })

    it('posts the tailored choice with the resume id', async () => {
      const calls = mockApi((req) =>
        req.method === 'POST'
          ? { body: sampleApplication({ stage: 'applied' }) }
          : detailHandler(readyToApply, [sampleEvent()], null, [approvedTailored, base])(req),
      )
      renderAt('/applications/1')
      await screen.findByRole('heading', { name: 'Northwind Freight' })

      const mark = within(section())
      fireEvent.click((await mark.findAllByRole('radio'))[0]) // the tailored resume
      fireEvent.click(mark.getByRole('button', { name: 'Mark as applied' }))

      await waitFor(() => expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
        choice: 'tailored',
        resume_id: 21,
      }))
    })

    it('toasts the API message when the apply is refused and stays open', async () => {
      mockApi((req) =>
        req.method === 'POST'
          ? { status: 409, body: { detail: { message: 'Approve this draft first' } } }
          : detailHandler(readyToApply, [sampleEvent()], null, [approvedTailored, base])(req),
      )
      renderAt('/applications/1')
      await screen.findByRole('heading', { name: 'Northwind Freight' })

      const mark = within(section())
      fireEvent.click((await mark.findAllByRole('radio'))[1])
      fireEvent.click(mark.getByRole('button', { name: 'Mark as applied' }))

      await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Approve this draft first'))
      expect(toast.success).not.toHaveBeenCalled()
      expect(within(section()).getAllByRole('radio')).toHaveLength(2)
    })

    it('says so when the options cannot be loaded', async () => {
      mockApi((req) =>
        req.path.endsWith('/submittable-resumes')
          ? { status: 404, body: { detail: 'application not found' } }
          : detailHandler(readyToApply)(req),
      )
      renderAt('/applications/1')
      await screen.findByRole('heading', { name: 'Northwind Freight' })

      expect(await within(section()).findByText('Could not load the resumes.')).toBeTruthy()
    })
  })

  describe('done', () => {
    const sent = sampleApplication({
      stage: 'applied',
      allowed_next_stages: ['screening', 'interviewing', 'rejected', 'withdrawn'],
      stage_change_hint: null,
      submitted_resume: { id: 21, kind: 'tailored', created_at: '2026-11-16T12:00:00Z' },
      applied_at: '2026-11-14T09:00:00Z',
      steps: sampleSteps(['done', 'Approved'], ['done', 'Approved'], ['done', 'Resume sent']),
    })

    it('shows a read-only line with the applied date and which resume was sent', async () => {
      await openDetail(sent)

      const mark = within(section())
      expect(mark.getByText(/Applied Nov 14 with the tailored resume/)).toBeTruthy()
      expect(mark.queryByRole('radio')).toBeNull()
      expect(mark.queryByRole('button')).toBeNull()
    })

    it('does not ask for the resume options', async () => {
      const calls = await openDetail(sent)

      expect(calls.some((c) => c.path.endsWith('/submittable-resumes'))).toBe(false)
    })
  })

  describe('not applied', () => {
    const withdrawn = sampleApplication({
      stage: 'withdrawn',
      allowed_next_stages: [],
      stage_change_hint: null,
      steps: sampleSteps(['done', 'Approved'], ['skipped', 'Skipped'], ['skipped', 'Withdrawn before applying']),
    })

    it('shows a read-only line saying it was withdrawn before applying', async () => {
      await openDetail(withdrawn)

      const mark = within(section())
      expect(mark.getByText('Withdrawn before applying')).toBeTruthy()
      expect(mark.queryByRole('radio')).toBeNull()
      expect(mark.queryByRole('button')).toBeNull()
    })

    it('does not ask for the resume options', async () => {
      const calls = await openDetail(withdrawn)

      expect(calls.some((c) => c.path.endsWith('/submittable-resumes'))).toBe(false)
    })
  })
})

describe('the Change stage control for a Saved application', () => {
  function openMenu() {
    fireEvent.keyDown(screen.getByRole('button', { name: /change stage/i }), { key: 'Enter' })
  }

  it('shows the API hint beside the control and offers Withdrawn only', async () => {
    await openDetail(sampleApplication())

    expect(screen.getByText('Apply in step 3 below')).toBeTruthy()
    openMenu()
    expect((await screen.findAllByRole('menuitem')).map((i) => i.textContent)).toEqual([
      'Withdrawn',
    ])
  })

  it('shows no hint when the API sends none', async () => {
    await openDetail(
      sampleApplication({
        stage: 'applied',
        allowed_next_stages: ['screening'],
        stage_change_hint: null,
      }),
    )

    expect(screen.queryByText('Apply in step 3 below')).toBeNull()
  })

  it('shows whatever hint the API sends', async () => {
    await openDetail(sampleApplication({ stage_change_hint: 'Use the other form' }))

    expect(screen.getByText('Use the other form')).toBeTruthy()
    expect(screen.queryByText('Apply in step 3 below')).toBeNull()
  })
})

describe('the steps stay current as the user works', () => {
  it('refreshes the strip when the posting analysis is approved', async () => {
    let current: Record<string, unknown> = sampleApplication()
    let analysis: Record<string, unknown> = sampleAnalysis()
    const calls = mockApi(({ method, path }) => {
      if (path.endsWith('/coverage')) return { status: 404, body: { detail: 'not found' } }
      if (method === 'POST' && path === '/api/analyses/5/approve') {
        analysis = { ...analysis, status: 'approved', reviewed_at: '2026-11-17T09:00:00Z' }
        current = sampleApplication({
          steps: sampleSteps(['done', 'Approved'], ['current', 'Write a tailored draft']),
        })
        return { body: analysis }
      }
      return detailHandler(current, [sampleEvent()], analysis, [base])({
        method,
        path,
        body: undefined,
      })
    })
    renderAt('/applications/1')
    await screen.findByRole('heading', { name: 'Northwind Freight' })

    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))

    await waitFor(() => {
      const first = within(screen.getByRole('list', { name: 'Workflow steps' })).getAllByRole(
        'listitem',
      )[0]
      expect(first.getAttribute('data-status')).toBe('done')
    })
    expect(calls.filter((c) => c.method === 'GET' && c.path === '/api/applications/1').length).toBe(2)
  })
})

describe('the applications list', () => {
  const sentTailored = sampleApplication({
    id: 2,
    company: 'Tallgrass Payments',
    stage: 'applied',
    submitted_resume: { id: 21, kind: 'tailored', created_at: '2026-11-16T12:00:00Z' },
  })
  const sentBase = sampleApplication({
    id: 3,
    company: 'Brightwell Labs',
    stage: 'screening',
    submitted_resume: { id: 30, kind: 'base', created_at: '2026-11-16T12:00:00Z' },
  })
  const notSent = sampleApplication({ id: 4, company: 'Juniper Analytics' })

  it('has a Resume sent column between Stage and Last activity', async () => {
    mockApi(() => ({ body: sampleList([notSent]) }))
    renderAt('/')

    await screen.findByRole('link', { name: 'Juniper Analytics' })
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['Company', 'Role', 'Source', 'Stage', 'Resume sent', 'Last activity'])
  })

  it('says Base, Tailored or Not sent yet, from what the API sends', async () => {
    mockApi(() => ({ body: sampleList([sentTailored, sentBase, notSent]) }))
    renderAt('/')

    const cell = async (company: string) => {
      const row = (await screen.findByRole('link', { name: company })).closest('tr')!
      return within(row).getAllByRole('cell')[4].textContent
    }
    expect(await cell('Tallgrass Payments')).toBe('Tailored')
    expect(await cell('Brightwell Labs')).toBe('Base')
    expect(await cell('Juniper Analytics')).toBe('Not sent yet')
  })

  it('keeps the empty-state row across every column', async () => {
    mockApi(() => ({ body: sampleList([]) }))
    renderAt('/')

    const message = await screen.findByText('No applications yet.')
    expect(message.getAttribute('colspan')).toBe('6')
  })
})
