import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  mockApi,
  renderAt,
  sampleAnalysis,
  sampleApplication,
  sampleEvent,
} from '@/test-utils'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

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

const LOCKED_TEXT = 'Approve the posting analysis to unlock tailoring'

function sampleDraft(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    application_id: 1,
    status: 'draft',
    prompt_version: 'v1',
    content_markdown: '# Jordan Avery\n\n## Summary\nBackend lead on Ruby on Rails.',
    created_at: '2026-11-16T12:00:00Z',
    guardrail_flags: [],
    ...overrides,
  }
}

const approved = () => sampleAnalysis({ status: 'approved' })

/** A detail page with an analysis and tailored drafts. POST adds a draft, newest first. */
function tailoringApi(
  analysis: Record<string, unknown> | null,
  drafts: Record<string, unknown>[] = [],
  post: { status: number; body: unknown } | null = null,
) {
  const list = [...drafts]
  return mockApi(({ method, path }) => {
    if (path === '/api/applications/1') return { body: sampleApplication() }
    if (path === '/api/applications/1/timeline') return { body: [sampleEvent()] }
    if (path === '/api/applications/1/analysis') return { body: analysis }
    if (path === '/api/applications/1/tailored-resumes' && method === 'GET') return { body: list }
    if (path === '/api/applications/1/tailored-resumes' && method === 'POST') {
      if (post) return post
      const draft = sampleDraft({
        id: 100 + list.length,
        content_markdown: '## Summary\nA newer draft.',
        created_at: '2026-11-18T12:00:00Z',
      })
      list.unshift(draft)
      return { status: 201, body: draft }
    }
    return { status: 404, body: { detail: 'not found' } }
  })
}

async function openSection() {
  return within(await screen.findByRole('region', { name: 'Tailored resume' }))
}

function postsTo(calls: { method: string; path: string }[]) {
  return calls.filter((c) => c.method === 'POST').map((c) => c.path)
}

describe('locked state', () => {
  it.each([
    ['no analysis', null],
    ['a draft analysis', sampleAnalysis({ status: 'draft' })],
    ['a rejected analysis', sampleAnalysis({ status: 'rejected' })],
  ])('shows the lock message and a disabled button for %s', async (_name, analysis) => {
    tailoringApi(analysis)
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText(LOCKED_TEXT)).toBeTruthy()
    expect(section.getByTestId('tailoring-lock')).toBeTruthy()
    expect((section.getByRole('button', { name: 'Tailor resume' }) as HTMLButtonElement).disabled).toBe(
      true,
    )
  })

  it('sits below the posting and analysis cards, above the timeline', async () => {
    tailoringApi(null)
    renderAt('/applications/1')

    const section = await screen.findByRole('region', { name: 'Tailored resume' })
    const analysis = screen.getByRole('region', { name: 'Posting analysis' })
    const timeline = await screen.findByText('Timeline')
    expect(analysis.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(section.compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('ready state', () => {
  it('has no lock and an enabled Tailor resume button', async () => {
    tailoringApi(approved())
    renderAt('/applications/1')

    const section = await openSection()
    await waitFor(() => expect(section.queryByText(LOCKED_TEXT)).toBeNull())
    expect(section.queryByTestId('tailoring-lock')).toBeNull()
    expect((section.getByRole('button', { name: 'Tailor resume' }) as HTMLButtonElement).disabled).toBe(
      false,
    )
  })

  it('Tailor resume posts to the API and then shows the draft', async () => {
    const calls = tailoringApi(approved())
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name: 'Tailor resume' }))

    const section = await openSection()
    expect(await section.findByText('Draft')).toBeTruthy()
    expect(postsTo(calls)).toEqual(['/api/applications/1/tailored-resumes'])
  })
})

describe('draft state', () => {
  it('shows the badge, the prompt version and date, Tailor again and the draft', async () => {
    tailoringApi(approved(), [sampleDraft()])
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Draft')).toBeTruthy()
    expect(section.getByText('Prompt v1 · Generated Nov 16')).toBeTruthy()
    expect(section.getByRole('button', { name: 'Tailor again' })).toBeTruthy()
    expect(section.getByText(/Backend lead on Ruby on Rails/)).toBeTruthy()
    expect(section.queryByText(LOCKED_TEXT)).toBeNull()
  })

  it('shows the draft read-only, with nothing to edit, approve or reject', async () => {
    tailoringApi(approved(), [sampleDraft()])
    renderAt('/applications/1')

    const section = await openSection()
    await section.findByText('Draft')
    expect(section.queryByRole('textbox')).toBeNull()
    expect(section.queryByRole('button', { name: /approve|reject|save/i })).toBeNull()
  })

  it('shows the newest draft', async () => {
    tailoringApi(approved(), [
      sampleDraft({ id: 8, content_markdown: 'The newest draft.' }),
      sampleDraft({ id: 7, content_markdown: 'An older draft.' }),
    ])
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('The newest draft.')).toBeTruthy()
    expect(section.queryByText('An older draft.')).toBeNull()
  })

  it('Tailor again posts a new request and shows the new draft', async () => {
    const calls = tailoringApi(approved(), [sampleDraft()])
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name: 'Tailor again' }))

    expect(await (await openSection()).findByText(/A newer draft/)).toBeTruthy()
    expect(postsTo(calls)).toEqual(['/api/applications/1/tailored-resumes'])
  })

  it('disables Tailor again when the analysis is no longer approved', async () => {
    tailoringApi(sampleAnalysis({ status: 'draft' }), [sampleDraft()])
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Draft')).toBeTruthy()
    expect((section.getByRole('button', { name: 'Tailor again' }) as HTMLButtonElement).disabled).toBe(
      true,
    )
  })
})

const KUBERNETES = { field: 'skill', value: 'Kubernetes', message: 'Skill "Kubernetes"' }
const FORTY = {
  field: 'number',
  value: '40%',
  message: 'Number "40%" in "Cut report run time by 40%…"',
}

describe('guardrail flags', () => {
  it('shows a warning box with the count, each flag and the closing line', async () => {
    tailoringApi(approved(), [sampleDraft({ guardrail_flags: [FORTY, KUBERNETES] })])
    renderAt('/applications/1')

    const box = within(await (await openSection()).findByRole('alert'))
    expect(box.getByText('2 things in this draft are not in your base resume')).toBeTruthy()
    expect(box.getByText('Number "40%" in "Cut report run time by 40%…"')).toBeTruthy()
    expect(box.getByText('Skill "Kubernetes"')).toBeTruthy()
    expect(
      box.getByText(
        'Edit or remove them, or keep them if they are true. Flags do not block approval.',
      ),
    ).toBeTruthy()
  })

  it('says "1 thing" and "is" for a single flag', async () => {
    tailoringApi(approved(), [sampleDraft({ guardrail_flags: [KUBERNETES] })])
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('1 thing in this draft is not in your base resume')).toBeTruthy()
  })

  it('shows no box when there are no flags', async () => {
    tailoringApi(approved(), [sampleDraft()])
    renderAt('/applications/1')

    const section = await openSection()
    await section.findByText('Draft')
    expect(section.queryByRole('alert')).toBeNull()
    expect(section.queryByText(/not in your base resume/)).toBeNull()
  })

  it('puts the box above the draft', async () => {
    tailoringApi(approved(), [sampleDraft({ guardrail_flags: [KUBERNETES] })])
    renderAt('/applications/1')

    const section = await openSection()
    const box = await section.findByRole('alert')
    const draft = section.getByText(/Backend lead on Ruby on Rails/)
    expect(box.compareDocumentPosition(draft) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows the flags of the newest draft, and no box when the newer draft has none', async () => {
    tailoringApi(approved(), [sampleDraft({ guardrail_flags: [KUBERNETES] })])
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByRole('alert')).toBeTruthy()
    fireEvent.click(section.getByRole('button', { name: 'Tailor again' }))

    expect(await (await openSection()).findByText(/A newer draft/)).toBeTruthy()
    expect((await openSection()).queryByRole('alert')).toBeNull()
  })
})

describe('while the call runs', () => {
  /** Makes the tailoring POST wait until the test releases it. Other calls are answered. */
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
    return () =>
      release(
        new Response(JSON.stringify(sampleDraft({ id: 9 })), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
  }

  it.each([
    ['Tailor resume', []],
    ['Tailor again', [sampleDraft()]],
  ])('%s shows a loading label and disables the button until it finishes', async (name, drafts) => {
    tailoringApi(approved(), drafts)
    const finish = holdPost()
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name }))

    await waitFor(async () => expect((await openSection()).getByText('Tailoring…')).toBeTruthy())
    const buttons = (await openSection()).getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
    for (const button of buttons) expect((button as HTMLButtonElement).disabled).toBe(true)

    finish()
    await waitFor(async () => expect((await openSection()).queryByText('Tailoring…')).toBeNull())
  })
})

describe('failures', () => {
  it.each([
    [502, 'The tailoring failed. Try again.'],
    [409, 'Save a base resume before tailoring.'],
  ])('toasts the API message on a %s and keeps the section as it was', async (status, detail) => {
    tailoringApi(approved(), [], { status, body: { detail } })
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name: 'Tailor resume' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(detail))
    const section = await openSection()
    expect(section.queryByText('Draft')).toBeNull()
    expect((section.getByRole('button', { name: 'Tailor resume' }) as HTMLButtonElement).disabled).toBe(
      false,
    )
  })
})
