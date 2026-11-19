import type { UseQueryResult } from '@tanstack/react-query'

import { InsightCard, SectionState } from '@/components/insights/SectionState'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { stageLabel } from '@/lib/applications'
import { formatDays, type PipelineMetrics } from '@/lib/metrics'

export function TimeInStageCard({ query }: { query: UseQueryResult<PipelineMetrics> }) {
  const rows = query.data?.time_in_stage ?? []
  const empty =
    query.data && rows.every((row) => row.sample_size === 0) ? 'No completed stages yet' : null

  return (
    <InsightCard
      title="Time in stage"
      description="Median days before moving on"
      className="lg:col-span-2"
    >
      <SectionState isPending={query.isPending} isError={query.isError} empty={empty}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Stage</TableHead>
              <TableHead className="text-right">Median</TableHead>
              <TableHead className="text-right">Sample</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.stage}>
                <TableCell>{stageLabel(row.stage)}</TableCell>
                <TableCell className="text-right font-semibold">
                  {formatDays(row.median_days)}
                </TableCell>
                <TableCell className="text-right">{row.sample_size}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SectionState>
    </InsightCard>
  )
}
