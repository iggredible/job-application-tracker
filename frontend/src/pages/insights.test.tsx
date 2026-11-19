import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { cloneElement, type ReactElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockApi, renderAt } from '@/test-utils'

// jsdom has no layout, so the real ResponsiveContainer measures 0 by 0 and draws nothing. Give
// the chart a fixed size instead.
vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) =>
    cloneElement(children, { width: 600, height: 220 }),
}))

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function rate(applied: number, responses: number, value: number | null) {
  return { applied, responses, rate: value }
}

function samplePipeline(overrides: Record<string, unknown> = {}) {
  return {
    total_applications: 40,
    applied_applications: 34,
    funnel: [
      { stage: 'applied', count: 34, share_of_previous: null },
      { stage: 'screening', count: 14, share_of_previous: 0.41176 },
      { stage: 'interviewing', count: 8, share_of_previous: 0.5714 },
      { stage: 'offer', count: 2, share_of_previous: 0.25 },
    ],
    time_in_stage: [
      { stage: 'saved', median_days: 2, sample_size: 34 },
      { stage: 'applied', median_days: 9.5, sample_size: 27 },
      { stage: 'screening', median_days: 1, sample_size: 11 },
      { stage: 'interviewing', median_days: null, sample_size: 0 },
    ],
    response: rate(34, 19, 19 / 34),
    stale_applications: 5,
    resume_comparison: {
      tailored: rate(18, 12, 12 / 18),
      base: rate(16, 7, 7 / 16),
    },
    ...overrides,
  }
}

function aiRow(overrides: Record<string, unknown> = {}) {
  return {
    feature: 'tailor_resume',
    prompt_version: 'v1',
    model: 'claude-test',
    calls: 12,
    failed_calls: 1,
    approved_as_is: 2,
    edited_then_approved: 6,
    rejected: 3,
    pending: 1,
    superseded: 4,
    avg_edit_ratio: 0.31,
    avg_flags_per_draft: 1.8,
    input_tokens: 1000,
    output_tokens: 500,
    estimated_cost: 0.524,
    median_latency_ms: 9600,
    ...overrides,
  }
}

const POSTING_ROW = aiRow({
  feature: 'posting_analysis',
  prompt_version: 'v1',
  calls: 24,
  failed_calls: 0,
  approved_as_is: 19,
  edited_then_approved: null,
  rejected: 3,
  pending: 1,
  superseded: 0,
  avg_edit_ratio: null,
  avg_flags_per_draft: null,
  estimated_cost: 0.31,
  median_latency_ms: 4200,
})

function sampleAI(rows: Record<string, unknown>[] = [POSTING_ROW, aiRow()]) {
  return { rows }
}

interface World {
  pipeline?: Record<string, unknown>
  ai?: Record<string, unknown>
  pipelineStatus?: number
  aiStatus?: number
}

function serve(world: World = {}) {
  return mockApi(({ path }) =>
    path === '/api/metrics/pipeline'
      ? { status: world.pipelineStatus, body: world.pipeline ?? samplePipeline() }
      : { status: world.aiStatus, body: world.ai ?? sampleAI() },
  )
}

async function open(world: World = {}) {
  const calls = serve(world)
  const view = renderAt('/insights')
  return { calls, ...view }
}

/** A section, once it has stopped loading. */
async function region(name: string) {
  const section = await screen.findByRole('region', { name })
  await waitFor(() => expect(within(section).queryByRole('status')).toBeNull())
  return section
}

const AI_CARD = 'AI calls by feature and prompt version'

describe('Insights page', () => {
  it('is reached from the nav and asks for each metrics endpoint once', async () => {
    const calls = serve()
    renderAt('/')
    fireEvent.click(screen.getByRole('link', { name: 'Insights' }))

    expect(await screen.findByRole('heading', { name: 'Insights', level: 1 })).toBeTruthy()
    await region('Funnel')
    await region(AI_CARD)
    const metrics = calls.filter((c) => c.path.startsWith('/api/metrics'))
    expect(metrics.map((c) => c.path).sort()).toEqual(['/api/metrics/ai', '/api/metrics/pipeline'])
  })

  it('has a Job search group and an AI performance group', async () => {
    await open()
    expect(await screen.findByRole('heading', { name: 'Job search' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'AI performance' })).toBeTruthy()
  })

  describe('stat tiles', () => {
    it('shows Applied of the total tracked, Response rate with both counts, and Stale', async () => {
      await open()

      const applied = await region('Applied')
      expect(within(applied).getByText('34')).toBeTruthy()
      expect(within(applied).getByText('of 40 tracked applications')).toBeTruthy()

      const response = screen.getByRole('region', { name: 'Response rate' })
      expect(within(response).getByText('56%')).toBeTruthy()
      expect(within(response).getByText('19 of 34 applied got a response')).toBeTruthy()

      const stale = screen.getByRole('region', { name: 'Stale applications' })
      expect(within(stale).getByText('5')).toBeTruthy()
    })

    it('shows n/a for the rate when nothing was applied, and keeps the counts', async () => {
      await open({
        pipeline: samplePipeline({
          total_applications: 3,
          applied_applications: 0,
          funnel: [],
          response: rate(0, 0, null),
          stale_applications: 0,
        }),
      })
      const response = await region('Response rate')
      expect(within(response).getByText('n/a')).toBeTruthy()
      expect(within(response).getByText('0 of 0 applied got a response')).toBeTruthy()
      const applied = screen.getByRole('region', { name: 'Applied' })
      expect(within(applied).getByText('of 3 tracked applications')).toBeTruthy()
    })
  })

  describe('funnel', () => {
    it('draws one bar per stage, labeled with the count and the share that moved on', async () => {
      await open()
      const funnel = await region('Funnel')

      await waitFor(() => {
        expect(funnel.querySelectorAll('.recharts-bar-rectangle').length).toBe(4)
      })
      // The count, and the share the API sent, rounded. The first stage has no share.
      expect(within(funnel).getByText('41% moved on')).toBeTruthy()
      expect(within(funnel).getByText('57% moved on')).toBeTruthy()
      expect(within(funnel).getByText('25% moved on')).toBeTruthy()
      expect(within(funnel).getAllByText(/% moved on/)).toHaveLength(3)
      for (const count of ['34', '14', '8', '2']) {
        expect(within(funnel).getByText(count)).toBeTruthy()
      }
      for (const stage of ['Applied', 'Screening', 'Interviewing', 'Offer']) {
        expect(within(funnel).getByText(stage)).toBeTruthy()
      }
    })

    it('is the only chart on the page', async () => {
      await open()
      await region('Funnel')
      expect(document.querySelectorAll('[data-slot="chart"]')).toHaveLength(1)
    })
  })

  describe('time in stage', () => {
    it('lists the median and the sample size for each stage the API returns', async () => {
      await open()
      const card = await region('Time in stage')
      const rows = within(card).getAllByRole('row').slice(1)
      expect(rows.map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))).toEqual([
        ['Saved', '2 days', '34'],
        ['Applied', '9.5 days', '27'],
        ['Screening', '1 day', '11'],
        ['Interviewing', 'n/a', '0'],
      ])
    })
  })

  describe('tailored vs base resume', () => {
    it('shows applied, responses and rate for each, with the sample size beside the rate', async () => {
      await open()
      const card = await region('Tailored vs base resume')
      const rows = within(card).getAllByRole('row').slice(1)
      expect(rows.map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))).toEqual([
        ['Tailored', '18', '12', '67%'],
        ['Base', '16', '7', '44%'],
      ])
    })

    it('says the samples are small and the comparison is not a controlled test', async () => {
      await open()
      const card = await region('Tailored vs base resume')
      const note = within(card).getByText(/small/i)
      expect(note.textContent).toMatch(/better-fit jobs/)
      expect(note.textContent).toMatch(/not a controlled test/)
    })

    it('shows n/a for a rate the API could not work out', async () => {
      await open({
        pipeline: samplePipeline({
          resume_comparison: { tailored: rate(0, 0, null), base: rate(2, 1, 0.5) },
        }),
      })
      const card = await region('Tailored vs base resume')
      const rows = within(card).getAllByRole('row').slice(1)
      expect(within(rows[0]).getAllByRole('cell').at(-1)?.textContent).toBe('n/a')
      expect(within(rows[1]).getAllByRole('cell').at(-1)?.textContent).toBe('50%')
    })
  })

  describe('AI performance table', () => {
    it('has a row for each feature, prompt version and model, with every column', async () => {
      await open()
      const card = await region(AI_CARD)
      const headers = within(card)
        .getAllByRole('columnheader')
        .map((h) => h.textContent)
      expect(headers).toEqual([
        'Feature',
        'Prompt',
        'Model',
        'Calls',
        'Failed',
        'Approved as is',
        'Edited, approved',
        'Rejected',
        'Pending',
        'Superseded',
        'Edit ratio',
        'Flags per draft',
        'Est. cost',
        'Median latency',
      ])
      const rows = within(card).getAllByRole('row').slice(1)
      expect(within(rows[1]).getAllByRole('cell').map((c) => c.textContent)).toEqual([
        'Tailor resume',
        'v1',
        'claude-test',
        '12',
        '1',
        '2',
        '6',
        '3',
        '1',
        '4',
        '31%',
        '1.8',
        '$0.52',
        '9.6 s',
      ])
    })

    it('shows n/a where a value does not apply', async () => {
      await open()
      const card = await region(AI_CARD)
      const row = within(card).getAllByRole('row')[1]
      const cells = within(row)
        .getAllByRole('cell')
        .map((c) => c.textContent)
      expect(cells[0]).toBe('Posting analysis')
      // Edited then approved, edit ratio and flags per draft.
      expect([cells[6], cells[10], cells[11]]).toEqual(['n/a', 'n/a', 'n/a'])
      expect(cells[12]).toBe('$0.31')
      expect(cells[13]).toBe('4.2 s')
    })

    it('keeps seeded calls apart from real ones by their model', async () => {
      await open({
        ai: sampleAI([aiRow({ model: 'seed' }), aiRow({ model: 'claude-test', calls: 3 })]),
      })
      const card = await region(AI_CARD)
      const rows = within(card).getAllByRole('row').slice(1)
      expect(rows).toHaveLength(2)
      expect(within(rows[0]).getByText('seed')).toBeTruthy()
      expect(within(rows[1]).getByText('claude-test')).toBeTruthy()
    })

    it('scrolls sideways on a narrow screen', async () => {
      await open()
      const card = await region(AI_CARD)
      const table = within(card).getByRole('table')
      expect(table.closest('[data-slot="table-container"]')?.className).toMatch(/overflow-x-auto/)
    })

    it('lets only the table scroll, not the page, by letting every grid around it shrink', async () => {
      await open()
      const card = await region(AI_CARD)
      // jsdom has no layout, so this checks the classes that make the browser do it: a grid
      // item is as wide as its content unless its column is minmax(0,1fr) or it has min-w-0.
      expect(card.className).toMatch(/\bmin-w-0\b/)
      for (let el = card.parentElement; el && el.tagName !== 'MAIN'; el = el.parentElement) {
        if (/\bgrid\b/.test(el.className)) {
          expect(el.className).toContain('grid-cols-[minmax(0,1fr)]')
        }
      }
    })
  })

  describe('loading states', () => {
    it('shows each section loading until its own request answers', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn((input: RequestInfo | URL) =>
          String(input) === '/api/metrics/pipeline'
            ? new Promise<Response>(() => {})
            : Promise.resolve(
                new Response(JSON.stringify(sampleAI()), {
                  headers: { 'Content-Type': 'application/json' },
                }),
              ),
        ),
      )
      renderAt('/insights')

      // The AI table does not wait for the pipeline request.
      const ai = await region(AI_CARD)
      expect(within(ai).getByRole('table')).toBeTruthy()
      for (const name of ['Funnel', 'Time in stage', 'Tailored vs base resume']) {
        const card = screen.getByRole('region', { name })
        expect(within(card).getByRole('status').textContent).toMatch(/loading/i)
      }
    })

    it('shows the AI table loading while the pipeline sections are filled', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn((input: RequestInfo | URL) =>
          String(input) === '/api/metrics/ai'
            ? new Promise<Response>(() => {})
            : Promise.resolve(
                new Response(JSON.stringify(samplePipeline()), {
                  headers: { 'Content-Type': 'application/json' },
                }),
              ),
        ),
      )
      renderAt('/insights')

      await region('Funnel')
      const ai = screen.getByRole('region', { name: AI_CARD })
      expect(within(ai).getByRole('status').textContent).toMatch(/loading/i)
    })
  })

  describe('empty states', () => {
    it('says so in each section when there is nothing to show', async () => {
      await open({
        pipeline: samplePipeline({
          total_applications: 0,
          applied_applications: 0,
          funnel: [],
          time_in_stage: [
            { stage: 'saved', median_days: null, sample_size: 0 },
            { stage: 'applied', median_days: null, sample_size: 0 },
          ],
          response: rate(0, 0, null),
          stale_applications: 0,
          resume_comparison: { tailored: rate(0, 0, null), base: rate(0, 0, null) },
        }),
        ai: sampleAI([]),
      })

      const funnel = await region('Funnel')
      await region(AI_CARD)
      expect(within(funnel).getByText('No applications have reached Applied yet')).toBeTruthy()
      expect(document.querySelectorAll('[data-slot="chart"]')).toHaveLength(0)
      expect(
        within(screen.getByRole('region', { name: 'Time in stage' })).getByText(
          'No completed stages yet',
        ),
      ).toBeTruthy()
      expect(
        within(screen.getByRole('region', { name: 'Tailored vs base resume' })).getByText(
          'No applications have been applied yet',
        ),
      ).toBeTruthy()
      expect(
        within(
          screen.getByRole('region', { name: AI_CARD }),
        ).getByText('No AI calls yet'),
      ).toBeTruthy()
      // The tiles still show their zeros.
      const applied = screen.getByRole('region', { name: 'Applied' })
      expect(within(applied).getByText('of 0 tracked applications')).toBeTruthy()
    })
  })

  describe('error states', () => {
    it('shows a message in the sections whose request failed, and only those', async () => {
      await open({ pipelineStatus: 500, pipeline: { detail: 'boom' } })

      const ai = await region(AI_CARD)
      expect(within(ai).getByRole('table')).toBeTruthy()
      for (const name of ['Funnel', 'Time in stage', 'Tailored vs base resume']) {
        const card = await region(name)
        expect(within(card).getByRole('alert').textContent).toMatch(/could not load/i)
      }
    })

    it('shows the pipeline sections when only the AI request failed', async () => {
      await open({ aiStatus: 500, ai: { detail: 'boom' } })
      await region('Funnel')
      const ai = await region(AI_CARD)
      expect(within(ai).getByRole('alert').textContent).toMatch(/could not load/i)
    })
  })
})
