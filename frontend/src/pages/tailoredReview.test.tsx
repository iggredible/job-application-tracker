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

const writeText = vi.fn()

beforeEach(() => {
  vi.mocked(toast.success).mockClear()
  vi.mocked(toast.error).mockClear()
  writeText.mockReset().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const BASE_TEXT = '# Jordan Avery\n\n## Skills\nRuby on Rails, PostgreSQL'
const DRAFT_TEXT = '# Jordan Avery\n\n## Summary\nBackend lead on Ruby on Rails.'
const KUBERNETES = { field: 'skill', value: 'Kubernetes', message: 'Skill "Kubernetes"' }
const FORTY = { field: 'number', value: '40%', message: 'Number "40%" in "Cut run time by 40%…"' }

function sampleDraft(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    application_id: 1,
    status: 'draft',
    prompt_version: 'v1',
    example_count: 0,
    content_markdown: DRAFT_TEXT,
    created_at: '2026-11-16T12:00:00Z',
    reviewed_at: null,
    guardrail_flags: [FORTY, KUBERNETES],
    outcome: 'pending',
    displayed: true,
    ...overrides,
  }
}

const BASE_COVERAGE = { covered: ['ruby on rails', 'postgresql'], missing: ['ci/cd', 'aws'] }

/** What GET /applications/1/coverage?resume_id=7 says: 50% for the base, 75% for the draft. */
function sampleCoverage(overrides: Record<string, unknown> = {}) {
  return {
    covered: ['ruby on rails', 'postgresql', 'ci/cd'],
    missing: ['aws'],
    ratio: 0.75,
    base: { ...BASE_COVERAGE, ratio: 0.5 },
    newly_covered: ['ci/cd'],
    still_missing: ['aws'],
    ...overrides,
  }
}

interface World {
  resumes?: Record<string, unknown>[]
  coverage?: Record<string, unknown>
  /** The answer to PATCH /resumes/{id}. By default the item with its new text and `coverage`. */
  patch?: (body: { content_markdown: string }) => { status?: number; body: unknown }
  decision?: { status: number; body: unknown }
}

/** A detail page with an approved analysis, a base resume and tailored resumes. The decisions and
 * the edit change the stored resumes, as the API would. */
function reviewApi(world: World = {}) {
  const resumes = [...(world.resumes ?? [sampleDraft()])]
  const coverage = world.coverage ?? sampleCoverage()
  const calls = mockApi(({ method, path, body }) => {
    if (path === '/api/applications/1') return { body: sampleApplication() }
    if (path === '/api/applications/1/timeline') return { body: [sampleEvent()] }
    if (path === '/api/applications/1/analysis') {
      return { body: sampleAnalysis({ status: 'approved' }) }
    }
    if (path === '/api/resume') {
      return {
        body: {
          id: 1,
          content_markdown: BASE_TEXT,
          status: 'approved',
          created_at: '2026-11-12T12:00:00Z',
          updated_at: '2026-11-12T12:00:00Z',
          reviewed_at: null,
        },
      }
    }
    if (path === '/api/applications/1/coverage') return { body: { ...BASE_COVERAGE, ratio: 0.5 } }
    if (path.startsWith('/api/applications/1/coverage?resume_id=')) return { body: coverage }
    if (path === '/api/applications/1/tailored-resumes' && method === 'GET') {
      return { body: resumes }
    }
    const edit = path.match(/^\/api\/resumes\/(\d+)$/)
    if (edit && method === 'PATCH') {
      const text = (body as { content_markdown: string }).content_markdown
      if (world.patch) return world.patch({ content_markdown: text })
      const index = resumes.findIndex((r) => r.id === Number(edit[1]))
      resumes[index] = { ...resumes[index], content_markdown: text, guardrail_flags: [] }
      return {
        body: { ...resumes[index], coverage: sampleCoverage({ ratio: 0.9, newly_covered: [] }) },
      }
    }
    const decide = path.match(/^\/api\/resumes\/(\d+)\/(approve|reject)$/)
    if (decide && method === 'POST') {
      if (world.decision) return world.decision
      const index = resumes.findIndex((r) => r.id === Number(decide[1]))
      const edited = resumes[index].content_markdown !== DRAFT_TEXT
      resumes[index] = {
        ...resumes[index],
        status: decide[2] === 'approve' ? 'approved' : 'rejected',
        reviewed_at: '2026-11-17T12:00:00Z',
        outcome:
          decide[2] === 'reject' ? 'rejected' : edited ? 'edited_then_approved' : 'approved',
      }
      return { body: resumes[index] }
    }
    return { status: 404, body: { detail: 'not found' } }
  })
  return calls
}

async function openSection() {
  return within(await screen.findByRole('region', { name: 'Tailored resume' }))
}

async function openDraft() {
  const section = await openSection()
  const textarea = (await section.findByLabelText('Draft (you can edit this)')) as HTMLTextAreaElement
  return { section, textarea }
}

function type(textarea: HTMLTextAreaElement, value: string) {
  fireEvent.change(textarea, { target: { value } })
}

const requests = (calls: { method: string; path: string }[], method: string) =>
  calls.filter((c) => c.method === method).map((c) => c.path)

describe('a draft awaiting review', () => {
  it('shows the base resume read-only beside an editable draft', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    expect(section.getByText('Base resume (read-only)')).toBeTruthy()
    expect(await section.findByText(/Ruby on Rails, PostgreSQL/)).toBeTruthy()
    expect(textarea.value).toBe(DRAFT_TEXT)
    expect(textarea.disabled).toBe(false)
    expect(section.getAllByRole('textbox')).toHaveLength(1) // the base resume is not editable
  })

  it('has Save edits, Reject and Approve buttons and the Draft badge', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section } = await openDraft()
    expect(section.getByText('Draft')).toBeTruthy()
    expect(section.getByRole('button', { name: 'Save edits' })).toBeTruthy()
    expect(section.getByRole('button', { name: 'Reject' })).toBeTruthy()
    expect(section.getByRole('button', { name: 'Approve' })).toBeTruthy()
    expect(section.queryByRole('button', { name: 'Copy Markdown' })).toBeNull()
  })

  it('keeps Save edits disabled until the text changes', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    const save = section.getByRole('button', { name: 'Save edits' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)

    type(textarea, `${DRAFT_TEXT}\nMore.`)
    expect(save.disabled).toBe(false)
  })
})

describe('keyword coverage under the panes', () => {
  it('shows base → draft as percentages with the newly covered and still missing keywords', async () => {
    const calls = reviewApi({
      coverage: sampleCoverage({
        ratio: 0.8,
        base: { ...BASE_COVERAGE, ratio: 0.6 },
        newly_covered: ['ci/cd', 'kubernetes'],
        still_missing: ['aws', 'react'],
      }),
    })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Keyword coverage 60% → 80%')).toBeTruthy()
    expect(section.getByText(/Newly covered: ci\/cd, kubernetes/)).toBeTruthy()
    expect(section.getByText(/Still missing: aws, react/)).toBeTruthy()
    expect(calls.map((c) => c.path)).toContain('/api/applications/1/coverage?resume_id=7')
  })

  it('says none when a list is empty', async () => {
    reviewApi({ coverage: sampleCoverage({ newly_covered: [], still_missing: [] }) })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText(/Newly covered: none/)).toBeTruthy()
    expect(section.getByText(/Still missing: none/)).toBeTruthy()
  })
})

describe('saving edits', () => {
  it('sends the text to PATCH /resumes/{id} and nothing else', async () => {
    const calls = reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, `${DRAFT_TEXT}\nAn extra line.`)
    fireEvent.click(section.getByRole('button', { name: 'Save edits' }))

    await waitFor(() => expect(requests(calls, 'PATCH')).toEqual(['/api/resumes/7']))
    const patch = calls.find((c) => c.method === 'PATCH')
    expect(patch?.body).toEqual({ content_markdown: `${DRAFT_TEXT}\nAn extra line.` })
    expect(requests(calls, 'POST')).toEqual([])
  })

  it('updates the flags and the coverage from the response once saved', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    expect(await section.findByText('Keyword coverage 50% → 75%')).toBeTruthy()
    expect(section.getByText('2 things in this draft are not in your base resume')).toBeTruthy()

    type(textarea, `${DRAFT_TEXT}\nAn extra line.`)
    fireEvent.click(section.getByRole('button', { name: 'Save edits' }))

    expect(await section.findByText('Keyword coverage 50% → 90%')).toBeTruthy()
    await waitFor(() => expect(section.queryByRole('alert')).toBeNull()) // the new flags are none
    expect((section.getByRole('button', { name: 'Save edits' }) as HTMLButtonElement).disabled).toBe(
      true,
    )
  })

  it('does not change the flags or the coverage while typing', async () => {
    const calls = reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    await section.findByText('Keyword coverage 50% → 75%')
    const before = calls.length

    type(textarea, 'Something else entirely, with Kubernetes and 40% and more.')

    expect(section.getByText('Keyword coverage 50% → 75%')).toBeTruthy()
    expect(section.getByText('2 things in this draft are not in your base resume')).toBeTruthy()
    expect(calls.length).toBe(before) // no request is made while typing
  })

  it('toasts the API message when saving is refused and keeps the typed text', async () => {
    reviewApi({ patch: () => ({ status: 409, body: { detail: 'only a draft can be edited' } }) })
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, 'My unsaved text')
    fireEvent.click(section.getByRole('button', { name: 'Save edits' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('only a draft can be edited'),
    )
    expect(textarea.value).toBe('My unsaved text')
  })

  it('disables the buttons while the save is running', async () => {
    let release: (response: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => (release = resolve))
    reviewApi()
    const answer = globalThis.fetch
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
        init?.method === 'PATCH' ? pending : answer(input, init),
      ),
    )
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, 'Edited')
    fireEvent.click(section.getByRole('button', { name: 'Save edits' }))

    await waitFor(() => {
      for (const name of ['Save edits', 'Reject', 'Approve']) {
        expect((section.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true)
      }
    })
    release(
      new Response(JSON.stringify({ ...sampleDraft({ content_markdown: 'Edited' }), coverage: sampleCoverage() }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await waitFor(() =>
      expect((section.getByRole('button', { name: 'Approve' }) as HTMLButtonElement).disabled).toBe(false),
    )
  })
})

describe('Tailor again with unsaved text', () => {
  const tailorAgain = (section: ReturnType<typeof within>) =>
    section.getByRole('button', { name: 'Tailor again' }) as HTMLButtonElement

  it('is disabled while the draft has unsaved text, so a new draft cannot replace it', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    expect(tailorAgain(section).disabled).toBe(false)

    type(textarea, `${DRAFT_TEXT}\nAn unsaved line.`)

    expect(tailorAgain(section).disabled).toBe(true)
  })

  it('is enabled again once the text is changed back or saved', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, `${DRAFT_TEXT}\nAn unsaved line.`)
    type(textarea, DRAFT_TEXT)
    expect(tailorAgain(section).disabled).toBe(false)

    type(textarea, `${DRAFT_TEXT}\nAn unsaved line.`)
    fireEvent.click(section.getByRole('button', { name: 'Save edits' }))

    await waitFor(() => expect(tailorAgain(section).disabled).toBe(false))
  })

  it('is enabled on the approved resume after a draft with unsaved text is rejected', async () => {
    reviewApi({
      resumes: [
        sampleDraft({ id: 8, content_markdown: 'Newer draft.' }),
        sampleDraft({
          id: 7,
          status: 'approved',
          outcome: 'approved',
          displayed: false,
          reviewed_at: '2026-11-16T12:00:00Z',
        }),
      ],
    })
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, 'Unsaved text')
    fireEvent.click(section.getByRole('button', { name: 'Reject' }))

    await waitFor(() => expect(section.queryByLabelText('Draft (you can edit this)')).toBeNull())
    expect(tailorAgain(section).disabled).toBe(false)
  })
})

describe('approving and rejecting', () => {
  it('Approve with no unsaved edits posts the approval only', async () => {
    const calls = reviewApi()
    renderAt('/applications/1')

    const { section } = await openDraft()
    fireEvent.click(section.getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(requests(calls, 'POST')).toEqual(['/api/resumes/7/approve']))
    expect(requests(calls, 'PATCH')).toEqual([])
  })

  it('Approve with unsaved edits saves them first, then approves', async () => {
    const calls = reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, `${DRAFT_TEXT}\nAn unsaved line.`)
    fireEvent.click(section.getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(requests(calls, 'POST')).toEqual(['/api/resumes/7/approve']))
    const order = calls
      .filter((c) => c.method === 'PATCH' || c.method === 'POST')
      .map((c) => `${c.method} ${c.path}`)
    expect(order).toEqual(['PATCH /api/resumes/7', 'POST /api/resumes/7/approve'])
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      content_markdown: `${DRAFT_TEXT}\nAn unsaved line.`,
    })
  })

  it('does not approve when saving the edits fails', async () => {
    const calls = reviewApi({ patch: () => ({ status: 409, body: { detail: 'cannot be edited' } }) })
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, 'Unsaved')
    fireEvent.click(section.getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('cannot be edited'))
    expect(requests(calls, 'POST')).toEqual([])
  })

  it('Reject posts the rejection only, even with unsaved edits', async () => {
    const calls = reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, 'Unsaved')
    fireEvent.click(section.getByRole('button', { name: 'Reject' }))

    await waitFor(() => expect(requests(calls, 'POST')).toEqual(['/api/resumes/7/reject']))
    expect(requests(calls, 'PATCH')).toEqual([])
  })

  it('toasts the API message when a decision is refused', async () => {
    reviewApi({
      decision: { status: 409, body: { detail: 'cannot go from approved to rejected' } },
    })
    renderAt('/applications/1')

    const { section } = await openDraft()
    fireEvent.click(section.getByRole('button', { name: 'Reject' }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('cannot go from approved to rejected'),
    )
  })
})

describe('an approved resume', () => {
  const approvedDraft = (overrides: Record<string, unknown> = {}) =>
    sampleDraft({
      status: 'approved',
      reviewed_at: '2026-11-16T12:00:00Z',
      outcome: 'approved',
      guardrail_flags: [],
      ...overrides,
    })

  it('is read-only with an Approved badge, the date, Copy Markdown and Tailor again', async () => {
    reviewApi({ resumes: [approvedDraft()] })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Approved')).toBeTruthy()
    expect(section.getByText(/Approved Nov 16/)).toBeTruthy()
    expect(section.getByText(/Backend lead on Ruby on Rails/)).toBeTruthy()
    expect(section.getByRole('button', { name: 'Copy Markdown' })).toBeTruthy()
    expect(section.getByRole('button', { name: 'Tailor again' })).toBeTruthy()
    expect(section.queryByRole('textbox')).toBeNull()
    expect(section.queryByRole('button', { name: /save edits|approve|reject/i })).toBeNull()
    expect(section.queryByText('Base resume (read-only)')).toBeNull() // one pane, as in the design
  })

  it('says how many past examples the approved resume used', async () => {
    reviewApi({ resumes: [approvedDraft({ example_count: 2 })] })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText(/Approved Nov 16 · Prompt v1 · 2 past examples used/)).toBeTruthy()
  })

  it('says "after your edits" only when the outcome is edited then approved', async () => {
    reviewApi({ resumes: [approvedDraft({ outcome: 'edited_then_approved' })] })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText(/Approved Nov 16 after your edits/)).toBeTruthy()
  })

  it('does not say "after your edits" for an unedited approval', async () => {
    reviewApi({ resumes: [approvedDraft()] })
    renderAt('/applications/1')

    const section = await openSection()
    await section.findByText(/Approved Nov 16/)
    expect(section.queryByText(/after your edits/)).toBeNull()
  })

  it('Copy Markdown copies the resume text to the clipboard', async () => {
    reviewApi({ resumes: [approvedDraft({ content_markdown: '# Final text' })] })
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name: 'Copy Markdown' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('# Final text'))
    expect(toast.success).toHaveBeenCalled()
  })

  it('toasts an error when the clipboard cannot be written', async () => {
    writeText.mockRejectedValue(new Error('denied'))
    reviewApi({ resumes: [approvedDraft()] })
    renderAt('/applications/1')

    fireEvent.click(await (await openSection()).findByRole('button', { name: 'Copy Markdown' }))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
  })

  it('still shows the keyword coverage line', async () => {
    reviewApi({ resumes: [approvedDraft()] })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Keyword coverage 50% → 75%')).toBeTruthy()
  })

  it('shows the approved state after approving a draft', async () => {
    reviewApi()
    renderAt('/applications/1')

    const { section, textarea } = await openDraft()
    type(textarea, `${DRAFT_TEXT}\nEdited.`)
    fireEvent.click(section.getByRole('button', { name: 'Approve' }))

    expect(await section.findByText(/Approved Nov 17 after your edits/)).toBeTruthy()
    expect(section.queryByRole('textbox')).toBeNull()
    expect(section.getByRole('button', { name: 'Copy Markdown' })).toBeTruthy()
  })
})

describe('a rejected resume', () => {
  it('is read-only with a Rejected badge and no Copy Markdown', async () => {
    reviewApi({
      resumes: [
        sampleDraft({
          status: 'rejected',
          reviewed_at: '2026-11-16T12:00:00Z',
          outcome: 'rejected',
          guardrail_flags: [],
        }),
      ],
    })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('Rejected')).toBeTruthy()
    expect(section.getByText(/Backend lead on Ruby on Rails/)).toBeTruthy()
    expect(section.queryByRole('textbox')).toBeNull()
    expect(section.queryByRole('button', { name: /save edits|approve|reject|copy/i })).toBeNull()
    expect(section.getByRole('button', { name: 'Tailor again' })).toBeTruthy()
  })

  it('shows the approved resume the API marks as displayed, not the newer rejected one', async () => {
    reviewApi({
      resumes: [
        sampleDraft({
          id: 8,
          status: 'rejected',
          outcome: 'rejected',
          displayed: false,
          content_markdown: 'The newer rejected one.',
        }),
        sampleDraft({
          id: 7,
          status: 'approved',
          outcome: 'approved',
          reviewed_at: '2026-11-16T12:00:00Z',
          content_markdown: 'The approved one.',
        }),
      ],
    })
    renderAt('/applications/1')

    const section = await openSection()
    expect(await section.findByText('The approved one.', { exact: false })).toBeTruthy()
    expect(section.queryByText('The newer rejected one.', { exact: false })).toBeNull()
  })
})
