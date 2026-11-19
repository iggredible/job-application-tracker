import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAddNote, useTimeline } from '@/hooks/useApplications'
import { formatDateTime, stageLabel, type TimelineEvent } from '@/lib/applications'

function describe(event: TimelineEvent): { title: string; detail: string } {
  if (event.type === 'note') return { title: 'Note', detail: event.note ?? '' }
  const to = event.to_stage ? stageLabel(event.to_stage) : ''
  const detail = event.from_stage ? `${stageLabel(event.from_stage)} → ${to}` : `Created in ${to}`
  return { title: 'Stage change', detail }
}

/** The application's history, newest first (the API sends it in that order), plus a note form. */
export function Timeline({ applicationId }: { applicationId: number }) {
  const { data: events, isPending, isError } = useTimeline(applicationId)
  const addNote = useAddNote(applicationId)
  const [note, setNote] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (note.trim() === '') return
    addNote.mutate(note.trim(), {
      onSuccess: () => setNote(''),
      onError: (error) => toast.error(error.message || 'Could not add the note'),
    })
  }

  return (
    <section>
      <Card>
        <CardHeader>
          <h2 className="font-heading text-base font-medium">Timeline</h2>
        </CardHeader>
        <CardContent className="grid gap-4">
          <form onSubmit={handleSubmit} className="grid gap-2">
            <Label htmlFor="timeline-note">Add a note</Label>
            <div className="flex gap-2">
              <Input
                id="timeline-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="For example: phone screen booked for Thursday"
              />
              <Button
                type="submit"
                variant="outline"
                disabled={note.trim() === '' || addNote.isPending}
              >
                Add note
              </Button>
            </div>
          </form>

          {isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">Could not load the timeline.</p>}
          {events && (
            <ol className="divide-y border-t">
              {events.map((event) => {
                const { title, detail } = describe(event)
                return (
                  <li key={event.id} className="grid grid-cols-[9rem_1fr] gap-4 py-3 text-sm">
                    <span className="text-muted-foreground">{formatDateTime(event.created_at)}</span>
                    <div>
                      <p className="font-medium">{title}</p>
                      <p className="whitespace-pre-wrap text-muted-foreground">{detail}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
