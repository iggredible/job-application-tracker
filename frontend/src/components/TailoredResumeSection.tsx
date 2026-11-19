import { Loader2, Lock, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useTailoredResumes, useTailorResume } from '@/hooks/useTailoredResumes'
import { formatDay } from '@/lib/applications'
import type { GuardrailFlag } from '@/lib/tailoredResumes'

/** The Tailored resume section: locked until the posting analysis is approved, then ready, then
 * showing the newest draft read-only. The API refuses a tailoring without an approved analysis;
 * the section only mirrors that by disabling its buttons. */
export function TailoredResumeSection({ applicationId }: { applicationId: number }) {
  const { data: analysis, isPending: analysisPending } = useAnalysis(applicationId)
  const { data: drafts, isPending: draftsPending, isError } = useTailoredResumes(applicationId)
  const run = useTailorResume(applicationId)

  const unlocked = analysis?.status === 'approved'
  const latest = drafts?.[0]

  function tailor() {
    run.mutate(undefined, {
      onError: (error) => toast.error(error.message || 'The tailoring failed. Try again.'),
    })
  }

  const label = (idle: string) =>
    run.isPending ? (
      <>
        <Loader2 className="animate-spin" aria-hidden="true" />
        Tailoring…
      </>
    ) : (
      idle
    )

  if (analysisPending || draftsPending || isError) {
    return (
      <section aria-label="Tailored resume">
        <p className={isError ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
          {isError ? 'Could not load the tailored resumes.' : 'Loading…'}
        </p>
      </section>
    )
  }

  if (!latest) {
    return (
      <section aria-label="Tailored resume" aria-busy={run.isPending}>
        {/* The Card draws its outline with a ring, so swap it for a dashed border. */}
        <Card className="border border-dashed border-foreground/30 ring-0">
          <CardContent className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              {!unlocked && (
                <Lock
                  className="mt-1 size-4 text-muted-foreground"
                  aria-hidden="true"
                  data-testid="tailoring-lock"
                />
              )}
              <div>
                <h2 className="text-lg font-semibold">Tailored resume</h2>
                <p className="text-sm text-muted-foreground">
                  {unlocked
                    ? 'Write a draft from your base resume and the approved keywords.'
                    : 'Approve the posting analysis to unlock tailoring'}
                </p>
              </div>
            </div>
            <Button onClick={tailor} disabled={!unlocked || run.isPending}>
              {label('Tailor resume')}
            </Button>
          </CardContent>
        </Card>
      </section>
    )
  }

  return (
    <section aria-label="Tailored resume" aria-busy={run.isPending}>
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-2">
          <CardTitle className="text-lg">Tailored resume</CardTitle>
          <Badge variant="outline">
            {latest.status.charAt(0).toUpperCase() + latest.status.slice(1)}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {`Prompt ${latest.prompt_version} · Generated ${formatDay(latest.created_at)}`}
          </span>
          <Button
            variant="outline"
            className="ml-auto"
            onClick={tailor}
            disabled={!unlocked || run.isPending}
          >
            {label('Tailor again')}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {latest.guardrail_flags.length > 0 && <FlagsBox flags={latest.guardrail_flags} />}
          <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/40 p-4 font-mono text-sm whitespace-pre-wrap">
            {latest.content_markdown}
          </pre>
        </CardContent>
      </Card>
    </section>
  )
}

/** The flags for the draft shown below it. The API sends the current flags, so editing updates
 * them; the box is not drawn when there are none. */
function FlagsBox({ flags }: { flags: GuardrailFlag[] }) {
  const many = flags.length !== 1
  return (
    <Alert className="border-amber-300 bg-amber-50 text-amber-950">
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>
        {`${flags.length} ${many ? 'things' : 'thing'} in this draft ${many ? 'are' : 'is'} not in your base resume`}
      </AlertTitle>
      <AlertDescription className="text-amber-900">
        <ul className="list-disc pl-5">
          {flags.map((flag) => (
            <li key={`${flag.field}:${flag.value}`}>{flag.message}</li>
          ))}
        </ul>
        <p>Edit or remove them, or keep them if they are true. Flags do not block approval.</p>
      </AlertDescription>
    </Alert>
  )
}
