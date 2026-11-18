import { Outlet } from 'react-router'

import { NavBar } from '@/components/NavBar'

export function Layout() {
  return (
    <div className="min-h-screen bg-muted/30">
      <NavBar />
      <main className="mx-auto max-w-7xl px-10 py-8">
        <Outlet />
      </main>
    </div>
  )
}
