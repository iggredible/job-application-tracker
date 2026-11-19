import { Loader2, Lock } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { useApply, useSubmittableResumes } from '@/hooks/useSubmission'
import { formatDay, type Application } from '@/lib/applications'
import type { ApplyInput, SubmittableResume } from '@/lib/submission'

const optionKey = (option: SubmittableResume) => `${option.kind}:${option.id}`

/** The line under an option's name: when it was saved or decided. A display label only. */
function describe(option: SubmittableResume): string {
  const day = formatDay(option.date)
  if (option.kind === 'base') return `Last saved ${day}`
  if (option.status === 'approved') return `Approved ${day}`
  if (option.status === 'rejected') return `Rejected ${day}`
  return `Draft from ${day}`
}

/**
 * The Mark as applied section. Which of its four states it is in comes from the status the API
 * gives step 3: locked, open (current or available), done, or skipped (withdrawn before
 * applying). The options and the reasons they are disabled come from the API too, so the page
 * works out nothing about which resume may be sent.
 */
export function MarkAsAppliedSection({ application }: { application: Application }) {
  const step = application.steps.find((s) => s.key === 'apply')
  const status = step?.status
  const open = status === 'current' || status === 'available'
  const { data: options, isPending, isError } = useSubmittableResumes(application.id, open)
  const apply = useApply(application.id)
  const [selected, setSelected] = useState('')

  function submit() {
    const option = options?.find((o) => optionKey(o) === selected)
    if (!option) return
    const input: ApplyInput =
      option.kind === 'base' ? { choice: 'base' } : { choice: 'tailored', resume_id: option.id }
    apply.mutate(input, {
      onSuccess: () => toast.success('Marked as applied'),
      onError: (error) => toast.error(error.message || 'Could not mark the application as applied'),
    })
  }

  if (status === 'locked') {
    return (
      <section aria-label="Mark as applied">
        {/* The Card draws its outline with a ring, so swap it for a dashed border. */}
        <Card className="border border-dashed border-foreground/30 ring-0">
          <CardContent className="flex items-start gap-3">
            <Lock className="mt-1 size-4 text-muted-foreground" aria-hidden="true" />
            <div>
              <h2 className="text-lg font-semibold">Mark as applied</h2>
              <p className="text-sm text-muted-foreground">
                Save a base resume to unlock this step.{' '}
                <Link to="/resume" className="underline">
                  Go to the Resume page
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    )
  }

  if (status === 'done' || status === 'skipped') {
    const sent = application.submitted_resume
    const line =
      status === 'skipped'
        ? 'Withdrawn before applying'
        : `Applied${application.applied_at ? ` ${formatDay(application.applied_at)}` : ''}${
            sent ? ` with the ${sent.kind === 'base' ? 'base' : 'tailored'} resume` : ''
          }`
    return (
      <section aria-label="Mark as applied">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Mark as applied</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{line}</p>
          </CardContent>
        </Card>
      </section>
    )
  }

  return (
    <section aria-label="Mark as applied" aria-busy={apply.isPending}>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Mark as applied</CardTitle>
          <p className="text-sm text-muted-foreground">
            Do this after you have submitted the application on the company&apos;s site.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm font-medium">Which resume did you send?</p>
          {isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">Could not load the resumes.</p>}
          {options && options.length === 0 && (
            <p className="text-sm text-muted-foreground">There is no resume to send yet.</p>
          )}
          {options && options.length > 0 && (
            <RadioGroup
              value={selected}
              onValueChange={setSelected}
              className="grid gap-3 md:grid-cols-2"
              aria-label="Which resume did you send?"
            >
              {options.map((option) => {
                const id = `submit-${optionKey(option)}`
                return (
                  <label
                    key={optionKey(option)}
                    htmlFor={id}
                    className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 has-[[data-state=checked]]:border-2 has-[[data-state=checked]]:border-foreground has-disabled:cursor-not-allowed has-disabled:opacity-60"
                  >
                    <RadioGroupItem
                      id={id}
                      value={optionKey(option)}
                      disabled={!option.submittable || apply.isPending}
                      className="mt-1"
                    />
                    <span className="grid gap-0.5">
                      <span className="text-sm font-semibold">
                        {option.kind === 'base' ? 'Base resume' : 'Tailored resume'}
                      </span>
                      <span className="text-sm text-muted-foreground">{describe(option)}</span>
                      {option.reason && (
                        <span className="text-sm text-muted-foreground">{option.reason}</span>
                      )}
                    </span>
                  </label>
                )
              })}
            </RadioGroup>
          )}
          <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-4">
            <p className="max-w-2xl text-sm text-muted-foreground">
              Moves the application from Saved to Applied, records today as the applied date and
              adds a timeline entry. The app does not submit anything for you.
            </p>
            <Button
              variant={status === 'current' ? 'default' : 'outline'}
              onClick={submit}
              disabled={!selected || apply.isPending}
            >
              {apply.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
              Mark as applied
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}
