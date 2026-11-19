import { Clock, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { ApplicationDialog } from '@/components/ApplicationDialog'
import { StageBadge } from '@/components/StageBadge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useApplications } from '@/hooks/useApplications'
import {
  formatDay,
  isStage,
  resumeSentLabel,
  sourceLabel,
  stageLabel,
  STAGES,
} from '@/lib/applications'

export function ApplicationsPage() {
  // The selected stage lives in the URL, so Back from a detail page keeps the filter.
  const [searchParams, setSearchParams] = useSearchParams()
  const param = searchParams.get('stage')
  const stage = isStage(param) ? param : undefined
  const { data, isPending, isError } = useApplications(stage)
  const [dialogOpen, setDialogOpen] = useState(false)
  const navigate = useNavigate()

  const counts = data?.counts_by_stage
  const total = counts ? STAGES.reduce((sum, s) => sum + counts[s], 0) : 0
  const staleCount = data?.stale_count ?? 0

  function select(next?: (typeof STAGES)[number]) {
    setSearchParams(next ? { stage: next } : {})
  }

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Applications</h1>
          {data && (
            <p className="mt-2 text-sm text-muted-foreground">
              {total} {total === 1 ? 'application' : 'applications'}
            </p>
          )}
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus /> New application
        </Button>
      </div>

      {counts && (
        <div className="mt-6 flex flex-wrap gap-2">
          <Pill selected={stage === undefined} onClick={() => select()} label="All" count={total} />
          {STAGES.map((s) => (
            <Pill
              key={s}
              selected={stage === s}
              onClick={() => select(s)}
              label={stageLabel(s)}
              count={counts[s]}
            />
          ))}
        </div>
      )}

      {staleCount > 0 && (
        <Alert className="mt-4 border-amber-300 bg-amber-50 text-amber-900">
          <Clock />
          <AlertDescription className="text-amber-900">
            {staleCount} {staleCount === 1 ? 'application has' : 'applications have'} had no
            recent activity.
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-6 rounded-xl border bg-background">
        {isPending && <p className="p-6 text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="p-6 text-sm text-destructive">Could not load applications.</p>}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Resume sent</TableHead>
                <TableHead>Last activity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-6 text-center text-muted-foreground">
                    {stage ? 'No applications in this stage.' : 'No applications yet.'}
                  </TableCell>
                </TableRow>
              )}
              {data.items.map((application) => (
                <TableRow key={application.id}>
                  <TableCell className="font-semibold">
                    <Link to={`/applications/${application.id}`} className="hover:underline">
                      {application.company}
                    </Link>
                  </TableCell>
                  <TableCell>{application.role}</TableCell>
                  <TableCell>{sourceLabel(application.source)}</TableCell>
                  <TableCell>
                    <StageBadge stage={application.stage} />
                  </TableCell>
                  <TableCell>{resumeSentLabel(application.submitted_resume)}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      {formatDay(application.last_activity_at)}
                      {application.is_stale && (
                        <Badge
                          variant="outline"
                          className="border-amber-400 bg-amber-50 text-amber-900"
                        >
                          Stale, {application.idle_days} days
                        </Badge>
                      )}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <ApplicationDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={(saved) => navigate(`/applications/${saved.id}`)}
      />
    </div>
  )
}

function Pill({
  label,
  count,
  selected,
  onClick,
}: {
  label: string
  count: number
  selected: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant={selected ? 'default' : 'outline'}
      className="rounded-full"
      aria-pressed={selected}
      onClick={onClick}
    >
      {label} <span className={selected ? '' : 'text-muted-foreground'}>{count}</span>
    </Button>
  )
}
