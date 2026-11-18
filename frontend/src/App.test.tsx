import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { routes } from './routes'

// Vitest globals are off, so Testing Library does not clean up between tests on its own.
afterEach(cleanup)

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(<RouterProvider router={router} />)
}

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

  it('renders the placeholder page for each route', () => {
    for (const [path, heading] of [
      ['/resume', 'Resume'],
      ['/insights', 'Insights'],
      ['/applications/7', 'Application'],
    ] as const) {
      const { unmount } = renderAt(path)
      expect(screen.getByRole('heading', { name: heading })).toBeTruthy()
      unmount()
    }
  })
})
