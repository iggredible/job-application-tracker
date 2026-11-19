import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { ApplicationDialog } from '@/components/ApplicationDialog'
import { StageBadge } from '@/components/StageBadge'
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
import { formatAdded, sourceLabel } from '@/lib/applications'

export function ApplicationsPage() {
  const { data: applications, isPending, isError } = useApplications()
  const [dialogOpen, setDialogOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Applications</h1>
          {applications && (
            <p className="mt-2 text-sm text-muted-foreground">
              {applications.length} {applications.length === 1 ? 'application' : 'applications'}
            </p>
          )}
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus /> New application
        </Button>
      </div>

      <div className="mt-6 rounded-xl border bg-background">
        {isPending && <p className="p-6 text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="p-6 text-sm text-destructive">Could not load applications.</p>}
        {applications && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Added</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {applications.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                    No applications yet.
                  </TableCell>
                </TableRow>
              )}
              {applications.map((application) => (
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
                  <TableCell>{formatAdded(application.created_at)}</TableCell>
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
