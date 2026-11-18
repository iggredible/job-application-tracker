import { useState } from 'react'
import { useParams } from 'react-router'

import { ApplicationDialog } from '@/components/ApplicationDialog'
import { StageBadge } from '@/components/StageBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useApplication } from '@/hooks/useApplications'
import { ApiError } from '@/lib/api'
import { formatAdded, sourceLabel } from '@/lib/applications'

export function ApplicationDetailPage() {
  const { id } = useParams()
  const { data: application, isPending, error } = useApplication(Number(id))
  const [editOpen, setEditOpen] = useState(false)

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (error) {
    const missing = error instanceof ApiError && error.status === 404
    return (
      <p className="text-sm text-muted-foreground">
        {missing ? 'Application not found.' : 'Could not load the application.'}
      </p>
    )
  }

  return (
    <div className="grid gap-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">{application.company}</h1>
            <StageBadge stage={application.stage} />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {application.role} · Source: {sourceLabel(application.source)} · Added{' '}
            {formatAdded(application.created_at)}
          </p>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          Edit
        </Button>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Job posting</CardTitle>
          {application.posting_url && (
            <a
              href={application.posting_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm underline"
            >
              Open original
            </a>
          )}
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-y-auto rounded-lg border bg-muted/40 p-4 text-sm whitespace-pre-wrap">
            {application.posting_text}
          </div>
        </CardContent>
      </Card>

      <ApplicationDialog open={editOpen} onOpenChange={setEditOpen} application={application} />
    </div>
  )
}
