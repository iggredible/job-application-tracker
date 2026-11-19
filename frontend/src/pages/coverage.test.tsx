import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockApi, renderAt, sampleAnalysis, sampleApplication, sampleEvent } from '@/test-utils'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
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

const KEYWORDS = [
  'ruby on rails',
  'postgresql',
  'rest apis',
  'background jobs',
  'integrations',
  'team leadership',
  'ci/cd',
  'aws',
  'kubernetes',
  'react',
]

function sampleCoverage(overrides: Record<string, unknown> = {}) {
  return {
    covered: KEYWORDS.slice(0, 6),
    missing: KEYWORDS.slice(6),
    ratio: 0.6,
    ...overrides,
  }
}

interface World {
  analysis?: Record<string, unknown> | null
  /** null: no base resume (the API answers 404). */
  resume?: Record<string, unknown> | null
  /** null: the API answers 404 "analysis not found". */
  coverage?: Record<string, unknown> | null
}

const sampleResume = {
  id: 1,
  content_markdown: 'Ruby on Rails',
  status: 'approved',
  created_at: '2026-11-12T12:00:00Z',
  updated_at: '2026-11-12T12:00:00Z',
  reviewed_at: null,
}

/** A detail page. Approve and reject change the analysis, as the real API does. */
function detailApi(world: World = {}) {
  let analysis: Record<string, unknown> | null =
    world.analysis === undefined ? sampleAnalysis({ keywords: KEYWORDS }) : world.analysis
  const resume = world.resume === undefined ? sampleResume : world.resume
  let coverage = world.coverage === undefined ? sampleCoverage() : world.coverage
  const calls = mockApi(({ method, path }) => {
    if (path === '/api/applications/1') return { body: sampleApplication() }
    if (path === '/api/applications/1/timeline') return { body: [sampleEvent()] }
    if (path === '/api/applications/1/analysis' && method === 'GET') return { body: analysis }
    if (path === '/api/applications/1/analysis' && method === 'POST') {
      analysis = sampleAnalysis({ id: 9, keywords: KEYWORDS })
      coverage = sampleCoverage({ covered: [KEYWORDS[0]], missing: KEYWORDS.slice(1), ratio: 0.1 })
      return { status: 201, body: analysis }
    }
    if (path === '/api/analyses/5/approve') {
      analysis = { ...analysis, status: 'approved' }
      return { body: analysis }
    }
    if (path === '/api/resume') {
      return resume ? { body: resume } : { status: 404, body: { detail: 'resume not found' } }
    }
    if (path === '/api/applications/1/coverage') {
      return coverage
        ? { body: coverage }
        : { status: 404, body: { detail: 'analysis not found' } }
    }
    return { status: 404, body: { detail: 'not found' } }
  })
  return calls
}

async function openBlock() {
  const card = await screen.findByRole('region', { name: 'Posting analysis' })
  return within(await within(card).findByRole('region', { name: 'Keyword coverage' }))
}

const coverageCalls = (calls: { method: string; path: string }[]) =>
  calls.filter((c) => c.path.startsWith('/api/applications/1/coverage'))

describe('coverage block', () => {
  it('is titled "Keyword coverage, base resume" and shows the percentage and the count', async () => {
    detailApi()
    renderAt('/applications/1')

    const block = await openBlock()
    expect(block.getByText('Keyword coverage, base resume')).toBeTruthy()
    expect(await block.findByText('60%')).toBeTruthy()
    expect(block.getByText('(6 of 10)')).toBeTruthy()
  })

  it('draws a progress bar at the percentage', async () => {
    detailApi()
    renderAt('/applications/1')

    const bar = (await openBlock()).getByRole('progressbar')
    expect(bar.getAttribute('aria-valuenow')).toBe('60')
  })

  it('lists the covered keywords and the missing keywords as badges', async () => {
    detailApi()
    renderAt('/applications/1')

    const block = await openBlock()
    const covered = await block.findByRole('list', { name: 'Covered keywords' })
    const missing = block.getByRole('list', { name: 'Missing keywords' })
    expect(within(covered).getAllByRole('listitem').map((li) => li.textContent)).toEqual(
      KEYWORDS.slice(0, 6),
    )
    expect(within(missing).getAllByRole('listitem').map((li) => li.textContent)).toEqual(
      KEYWORDS.slice(6),
    )
  })

  it('rounds the ratio to a whole percent', async () => {
    detailApi({
      coverage: sampleCoverage({ covered: ['a', 'b'], missing: ['c'], ratio: 2 / 3 }),
    })
    renderAt('/applications/1')

    const block = await openBlock()
    expect(await block.findByText('67%')).toBeTruthy()
    expect(block.getByText('(2 of 3)')).toBeTruthy()
  })

  it('shows 100% and no Missing badges when everything is covered', async () => {
    detailApi({ coverage: sampleCoverage({ covered: KEYWORDS, missing: [], ratio: 1 }) })
    renderAt('/applications/1')

    const block = await openBlock()
    expect(await block.findByText('100%')).toBeTruthy()
    expect(block.getByText('(10 of 10)')).toBeTruthy()
    expect(block.queryByRole('list', { name: 'Missing keywords' })).toBeNull()
  })

  it('asks for the base resume, with no resume_id', async () => {
    const calls = detailApi()
    renderAt('/applications/1')

    await (await openBlock()).findByText('60%')
    expect(coverageCalls(calls).map((c) => c.path)).toEqual(['/api/applications/1/coverage'])
  })

  it('never calls the number an ATS score', async () => {
    detailApi()
    const { container } = renderAt('/applications/1')

    await (await openBlock()).findByText('60%')
    expect(container.textContent).not.toMatch(/ats/i)
  })
})

describe('no base resume', () => {
  it('shows a link to the Resume page in place of the numbers', async () => {
    detailApi({ resume: null })
    renderAt('/applications/1')

    const block = await openBlock()
    const link = await block.findByRole('link', { name: /resume/i })
    expect(link.getAttribute('href')).toBe('/resume')
    expect(block.queryByRole('progressbar')).toBeNull()
    expect(block.queryByText(/%/)).toBeNull()
    expect(block.queryByRole('list', { name: 'Covered keywords' })).toBeNull()
  })

  it('does not ask for coverage', async () => {
    const calls = detailApi({ resume: null })
    renderAt('/applications/1')

    await (await openBlock()).findByRole('link', { name: /resume/i })
    expect(coverageCalls(calls)).toEqual([])
  })
})

describe('nothing to show', () => {
  it('has no coverage block when there is no analysis', async () => {
    const calls = detailApi({ analysis: null, coverage: null })
    renderAt('/applications/1')

    await screen.findByText('No analysis yet')
    expect(screen.queryByRole('region', { name: 'Keyword coverage' })).toBeNull()
    expect(coverageCalls(calls)).toEqual([])
  })

  it('has no coverage block when the API has no analysis to use', async () => {
    const calls = detailApi({ analysis: sampleAnalysis({ status: 'rejected' }), coverage: null })
    renderAt('/applications/1')

    await screen.findByText('Rejected')
    await waitFor(() => expect(coverageCalls(calls).length).toBe(1))
    expect(screen.queryByRole('region', { name: 'Keyword coverage' })).toBeNull()
  })

  it('has no coverage block when the analysis has no keywords', async () => {
    detailApi({
      analysis: sampleAnalysis({ keywords: [] }),
      coverage: sampleCoverage({ covered: [], missing: [], ratio: 0 }),
    })
    renderAt('/applications/1')

    await screen.findByText('Draft')
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull())
    expect(screen.queryByRole('region', { name: 'Keyword coverage' })).toBeNull()
  })
})

describe('refreshing', () => {
  it('asks for coverage again after the analysis is approved', async () => {
    const calls = detailApi()
    renderAt('/applications/1')
    const block = await openBlock()
    await block.findByText('60%')
    const before = coverageCalls(calls).length

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(coverageCalls(calls).length).toBeGreaterThan(before))
  })

  it('shows the new numbers after Analyze again', async () => {
    detailApi()
    renderAt('/applications/1')
    const block = await openBlock()
    await block.findByText('60%')

    fireEvent.click(screen.getByRole('button', { name: 'Analyze again' }))

    expect(await (await openBlock()).findByText('10%')).toBeTruthy()
    expect((await openBlock()).getByText('(1 of 10)')).toBeTruthy()
  })
})
