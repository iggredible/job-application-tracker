import type { UseQueryResult } from '@tanstack/react-query'

import { InsightCard, SectionState } from '@/components/insights/SectionState'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  featureLabel,
  formatCost,
  formatCount,
  formatDecimal,
  formatLatency,
  formatPercent,
  type AIMetrics,
} from '@/lib/metrics'

const NUMERIC_HEADINGS = [
  'Calls',
  'Failed',
  'Approved as is',
  'Edited, approved',
  'Rejected',
  'Pending',
  'Superseded',
  'Edit ratio',
  'Flags per draft',
  'Est. cost',
  'Median latency',
]

export function AIPerformanceCard({ query }: { query: UseQueryResult<AIMetrics> }) {
  const rows = query.data?.rows ?? []
  const empty = query.data && rows.length === 0 ? 'No AI calls yet' : null

  return (
    <InsightCard
      title="AI calls by feature and prompt version"
      description="From the call log and the drafts each call produced. Lower edit ratio and fewer flags mean drafts needed less fixing."
    >
      <SectionState isPending={query.isPending} isError={query.isError} empty={empty}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Feature</TableHead>
              <TableHead>Prompt</TableHead>
              <TableHead>Model</TableHead>
              {NUMERIC_HEADINGS.map((heading) => (
                <TableHead key={heading} className="text-right whitespace-normal">
                  {heading}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={`${row.feature}/${row.prompt_version}/${row.model}`}>
                <TableCell>{featureLabel(row.feature)}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{row.prompt_version}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{row.model}</TableCell>
                <TableCell className="text-right">{row.calls}</TableCell>
                <TableCell className="text-right">{row.failed_calls}</TableCell>
                <TableCell className="text-right">{row.approved_as_is}</TableCell>
                <TableCell className="text-right">{formatCount(row.edited_then_approved)}</TableCell>
                <TableCell className="text-right">{row.rejected}</TableCell>
                <TableCell className="text-right">{row.pending}</TableCell>
                <TableCell className="text-right">{row.superseded}</TableCell>
                <TableCell className="text-right font-semibold">
                  {formatPercent(row.avg_edit_ratio)}
                </TableCell>
                <TableCell className="text-right font-semibold">
                  {formatDecimal(row.avg_flags_per_draft)}
                </TableCell>
                <TableCell className="text-right">{formatCost(row.estimated_cost)}</TableCell>
                <TableCell className="text-right">{formatLatency(row.median_latency_ms)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SectionState>
    </InsightCard>
  )
}
