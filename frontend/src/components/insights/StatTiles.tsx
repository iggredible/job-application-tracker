import type { UseQueryResult } from '@tanstack/react-query'

import { Card, CardContent } from '@/components/ui/card'
import { formatPercent, type PipelineMetrics } from '@/lib/metrics'

function Tile({
  label,
  query,
  value,
  detail,
}: {
  label: string
  query: UseQueryResult<PipelineMetrics>
  value: (data: PipelineMetrics) => string
  detail: (data: PipelineMetrics) => string
}) {
  const { data } = query
  return (
    <Card role="region" aria-label={label} className="min-w-0 gap-0 py-5">
      <CardContent className="flex flex-col gap-1 px-5">
        <p className="text-sm text-muted-foreground">{label}</p>
        {data ? (
          <>
            <p className="text-4xl font-semibold tracking-tight">{value(data)}</p>
            <p className="text-sm text-muted-foreground">{detail(data)}</p>
          </>
        ) : query.isError ? (
          <p role="alert" className="text-sm text-destructive">
            Could not load this section.
          </p>
        ) : (
          <p role="status" className="text-sm text-muted-foreground">
            Loading…
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function StatTiles({ query }: { query: UseQueryResult<PipelineMetrics> }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Tile
        label="Applied"
        query={query}
        value={(d) => String(d.applied_applications)}
        detail={(d) => `of ${d.total_applications} tracked applications`}
      />
      <Tile
        label="Response rate"
        query={query}
        value={(d) => formatPercent(d.response.rate)}
        detail={(d) => `${d.response.responses} of ${d.response.applied} applied got a response`}
      />
      <Tile
        label="Stale applications"
        query={query}
        value={(d) => String(d.stale_applications)}
        detail={() => 'no activity in 14 or more days'}
      />
    </div>
  )
}
