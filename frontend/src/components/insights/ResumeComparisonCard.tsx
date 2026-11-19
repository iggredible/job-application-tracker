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
import { formatPercent, type PipelineMetrics } from '@/lib/metrics'

export function ResumeComparisonCard({ query }: { query: UseQueryResult<PipelineMetrics> }) {
  const comparison = query.data?.resume_comparison
  const rows = comparison
    ? [
        { label: 'Tailored', ...comparison.tailored },
        { label: 'Base', ...comparison.base },
      ]
    : []
  const empty =
    comparison && rows.every((row) => row.applied === 0)
      ? 'No applications have been applied yet'
      : null

  return (
    <InsightCard
      title="Tailored vs base resume"
      description="Response rate by which resume was sent"
    >
      <SectionState isPending={query.isPending} isError={query.isError} empty={empty}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Resume sent</TableHead>
              <TableHead className="text-right">Applied</TableHead>
              <TableHead className="text-right">Responses</TableHead>
              <TableHead className="text-right">Response rate</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.label}>
                <TableCell>{row.label}</TableCell>
                <TableCell className="text-right">{row.applied}</TableCell>
                <TableCell className="text-right">{row.responses}</TableCell>
                <TableCell className="text-right font-semibold">
                  {formatPercent(row.rate)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="mt-4 text-sm text-muted-foreground">
          Small samples, and tailoring may go to better-fit jobs, so this comparison is not a
          controlled test. Read the difference as a hint, not proof.
        </p>
      </SectionState>
    </InsightCard>
  )
}
