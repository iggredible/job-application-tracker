import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'

import { routes } from './routes'

export function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...view, router }
}

export type ApiHandler = (req: { method: string; path: string; body: unknown }) => {
  status?: number
  body: unknown
}

export interface ApiCall {
  method: string
  path: string
  body: unknown
}

/** Replaces global fetch with a handler and records every call made through it. */
export function mockApi(handler: ApiHandler) {
  const calls: ApiCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      const path = String(input)
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
      calls.push({ method, path, body })
      const { status = 200, body: json } = handler({ method, path, body })
      return new Response(JSON.stringify(json), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
  return calls
}

const ALL_STAGES = [
  'saved',
  'applied',
  'screening',
  'interviewing',
  'offer',
  'accepted',
  'rejected',
  'withdrawn',
]

type Sample = Record<string, unknown> & { stage?: unknown; is_stale?: unknown }

/** The body of GET /applications: counts and the stale count are worked out from the items. */
export function sampleList(items: Sample[], overrides: Record<string, unknown> = {}) {
  const counts = Object.fromEntries(ALL_STAGES.map((s) => [s, 0]))
  for (const item of items) counts[String(item.stage)] += 1
  return {
    items,
    counts_by_stage: counts,
    stale_count: items.filter((i) => i.is_stale).length,
    ...overrides,
  }
}

export function sampleEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    application_id: 1,
    type: 'stage_change',
    from_stage: null,
    to_stage: 'saved',
    note: null,
    created_at: '2026-11-12T12:00:00Z',
    ...overrides,
  }
}

export function sampleAnalysis(overrides: Record<string, unknown> = {}) {
  return {
    id: 5,
    application_id: 1,
    status: 'draft',
    prompt_version: 'v1',
    requirements: [
      { text: 'Ruby on Rails services in production', category: 'must_have' },
      { text: 'PostgreSQL', category: 'must_have' },
      { text: 'CI/CD', category: 'nice_to_have' },
    ],
    keywords: ['ruby on rails', 'postgresql', 'ci/cd'],
    created_at: '2026-11-16T12:00:00Z',
    reviewed_at: null,
    ...overrides,
  }
}

/**
 * Answers the detail page's requests: the application, its timeline and its analysis (none
 * unless one is given), and no tailored resumes.
 */
export function detailHandler(
  application: Record<string, unknown> = sampleApplication(),
  timeline: Record<string, unknown>[] = [sampleEvent()],
  analysis: Record<string, unknown> | null = null,
): ApiHandler {
  return ({ path }) => ({
    body: path.endsWith('/timeline')
      ? timeline
      : path.endsWith('/analysis')
        ? analysis
        : path.endsWith('/tailored-resumes')
          ? []
          : application,
  })
}

export function sampleApplication(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    company: 'Northwind Freight',
    role: 'Senior Backend Engineer',
    source: 'linkedin',
    stage: 'saved',
    posting_url: 'https://northwind.example/careers/1',
    posting_text: 'Build services that book, track and settle every load.',
    created_at: '2026-11-12T12:00:00Z',
    updated_at: '2026-11-12T12:00:00Z',
    allowed_next_stages: ['applied', 'withdrawn'],
    last_activity_at: '2026-11-12T12:00:00Z',
    is_stale: false,
    idle_days: 0,
    ...overrides,
  }
}
