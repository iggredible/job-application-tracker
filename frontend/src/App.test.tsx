import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mockApi, renderAt, sampleList } from './test-utils'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() }, Toaster: () => null }))

beforeEach(() => {
  mockApi(() => ({ body: sampleList([]) }))
})

// Vitest globals are off, so Testing Library does not clean up between tests on its own.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('app shell', () => {
  it('shows the top nav with Applications, Resume and Insights', () => {
    renderAt('/')

    const nav = screen.getByRole('navigation')
    expect(nav.textContent).toContain('Job Tracker')
    expect(screen.getByRole('link', { name: 'Applications' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Resume' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Insights' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Applications' })).toBeTruthy()
  })

  it('links to the right paths and navigates when a nav link is clicked', async () => {
    renderAt('/')

    const applications = screen.getByRole('link', { name: 'Applications' })
    const resume = screen.getByRole('link', { name: 'Resume' })
    const insights = screen.getByRole('link', { name: 'Insights' })
    expect(applications.getAttribute('href')).toBe('/')
    expect(resume.getAttribute('href')).toBe('/resume')
    expect(insights.getAttribute('href')).toBe('/insights')
    expect(applications.getAttribute('aria-current')).toBe('page')

    fireEvent.click(resume)

    expect(await screen.findByRole('heading', { name: 'Resume' })).toBeTruthy()
    expect(resume.getAttribute('aria-current')).toBe('page')
    expect(applications.getAttribute('aria-current')).toBeNull()
  })

  it('renders the placeholder page for each route that is not built yet', () => {
    for (const [path, heading] of [
      ['/resume', 'Resume'],
      ['/insights', 'Insights'],
    ] as const) {
      const { unmount } = renderAt(path)
      expect(screen.getByRole('heading', { name: heading })).toBeTruthy()
      unmount()
    }
  })
})
