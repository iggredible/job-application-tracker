import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'

const links = [
  { to: '/', label: 'Applications', end: true },
  { to: '/resume', label: 'Resume', end: false },
  { to: '/insights', label: 'Insights', end: false },
]

export function NavBar() {
  return (
    <nav className="border-b bg-background">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-10">
        <span className="font-semibold">Job Tracker</span>
        <div className="flex h-full items-center gap-6">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                cn(
                  'flex h-full items-center border-b-2 text-sm transition-colors',
                  isActive
                    ? 'border-foreground font-medium text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}
