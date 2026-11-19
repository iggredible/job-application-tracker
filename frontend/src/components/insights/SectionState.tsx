import type { ReactNode } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/** The loading, error and empty bodies every section shares. `empty` is the message to show
 * when there is nothing to display, or null when there is. */
export function SectionState({
  isPending,
  isError,
  empty,
  children,
}: {
  isPending: boolean
  isError: boolean
  empty: string | null
  children: ReactNode
}) {
  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Loading…
      </p>
    )
  }
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Could not load this section.</AlertDescription>
      </Alert>
    )
  }
  if (empty !== null) return <p className="text-sm text-muted-foreground">{empty}</p>
  return <>{children}</>
}

/** A titled card, named for screen readers so each section can be found by its title. */
export function InsightCard({
  title,
  description,
  className,
  children,
}: {
  title: string
  description?: string
  className?: string
  children: ReactNode
}) {
  return (
    <Card role="region" aria-label={title} className={cn('min-w-0', className)}>
      <CardHeader className="gap-1 px-5">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="px-5">{children}</CardContent>
    </Card>
  )
}
