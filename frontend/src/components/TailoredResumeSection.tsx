import { Loader2, Lock, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useResumeCoverage } from '@/hooks/useCoverage'
import { useResume } from '@/hooks/useResume'
import {
  useReviewResume,
  useSaveEdits,
  useTailoredResumes,
  useTailorResume,
} from '@/hooks/useTailoredResumes'
import { formatDay } from '@/lib/applications'
import type { ResumeCoverage } from '@/lib/coverage'
import type { GuardrailFlag, TailoredResume } from '@/lib/tailoredResumes'

/** The Tailored resume section: locked until the posting analysis is approved, then ready, then
 * showing the resume the API marks as displayed: a draft to review beside the base resume, or an
 * approved or rejected one, read-only. The API refuses a tailoring without an approved analysis,
 * and an edit or a decision on a resume that is no longer a draft; the section only mirrors that
 * by what it shows and by disabling its buttons. */
export function TailoredResumeSection({ applicationId }: { applicationId: number }) {
  const { data: analysis, isPending: analysisPending } = useAnalysis(applicationId)
  const { data: drafts, isPending: draftsPending, isError } = useTailoredResumes(applicationId)
  const { data: baseResume } = useResume()
  const run = useTailorResume(applicationId)
  const save = useSaveEdits(applicationId)
  const review = useReviewResume(applicationId)

  const unlocked = analysis?.status === 'approved'
  const latest = drafts?.find((draft) => draft.displayed)
  const { data: coverage } = useResumeCoverage(applicationId, latest?.id ?? null)
  const busy = run.isPending || save.isPending || review.isPending
  // Whether the draft on screen has text that is not saved. Tailor again waits for it, because
  // the new draft would replace this one and the typed text would be lost.
  const [unsaved, setUnsaved] = useState(false)

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
            <Button onClick={tailor} disabled={!unlocked || busy}>
              {label('Tailor resume')}
            </Button>
          </CardContent>
        </Card>
      </section>
    )
  }

  const isDraft = latest.status === 'draft'

  return (
    <section aria-label="Tailored resume" aria-busy={busy}>
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-2">
          <CardTitle className="text-lg">Tailored resume</CardTitle>
          <Badge variant="outline">
            {latest.status.charAt(0).toUpperCase() + latest.status.slice(1)}
          </Badge>
          <span className="text-sm text-muted-foreground">{describe(latest)}</span>
          <div className="ml-auto flex gap-2">
            {latest.status === 'approved' && (
              <Button variant="outline" onClick={() => copy(latest.content_markdown)} disabled={busy}>
                Copy Markdown
              </Button>
            )}
            <Button
              variant="outline"
              onClick={tailor}
              disabled={!unlocked || busy || unsaved}
              title={unsaved ? 'Save your edits first' : undefined}
            >
              {label('Tailor again')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {latest.guardrail_flags.length > 0 && <FlagsBox flags={latest.guardrail_flags} />}
          {isDraft ? (
            <DraftReview
              key={latest.id}
              resume={latest}
              baseText={baseResume?.content_markdown ?? null}
              busy={busy}
              onUnsavedChange={setUnsaved}
              onSave={(text) =>
                save.mutate(
                  { resumeId: latest.id, text },
                  { onError: (error) => toast.error(error.message || 'Could not save the edits.') },
                )
              }
              onDecide={(decision, unsavedText) =>
                review.mutate(
                  { resumeId: latest.id, decision, unsavedText },
                  {
                    onError: (error) =>
                      toast.error(error.message || `Could not ${decision} the resume.`),
                  },
                )
              }
            />
          ) : (
            <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/40 p-4 font-mono text-sm whitespace-pre-wrap">
              {latest.content_markdown}
            </pre>
          )}
          {coverage && <CoverageLine coverage={coverage} />}
        </CardContent>
      </Card>
    </section>
  )
}

/** The line under the header: when the resume was approved, or when it was generated. The API
 * says whether an approved resume was edited. */
function describe(resume: TailoredResume): string {
  if (resume.status === 'approved' && resume.reviewed_at) {
    const edited = resume.outcome === 'edited_then_approved' ? ' after your edits' : ''
    return `Approved ${formatDay(resume.reviewed_at)}${edited} · Prompt ${resume.prompt_version}`
  }
  return `Prompt ${resume.prompt_version} · Generated ${formatDay(resume.created_at)}`
}

async function copy(markdown: string) {
  try {
    await navigator.clipboard.writeText(markdown)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Could not copy. Select the text and copy it instead.')
  }
}

/** The base resume beside the editable draft. The typed text is held here and goes to the API
 * only on Save edits or Approve, so the flags and the coverage change on save, not while typing. */
function DraftReview({
  resume,
  baseText,
  busy,
  onUnsavedChange,
  onSave,
  onDecide,
}: {
  resume: TailoredResume
  baseText: string | null
  busy: boolean
  onUnsavedChange: (unsaved: boolean) => void
  onSave: (text: string) => void
  onDecide: (decision: 'approve' | 'reject', unsavedText: string | null) => void
}) {
  const [text, setText] = useState(resume.content_markdown)
  const unsaved = text !== resume.content_markdown

  // Tell the section, and clear it when this draft goes away (a decision, or a newer draft).
  useEffect(() => {
    onUnsavedChange(unsaved)
    return () => onUnsavedChange(false)
  }, [unsaved, onUnsavedChange])

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <p className="text-sm font-medium">Base resume (read-only)</p>
          <pre className="h-96 overflow-auto rounded-lg border bg-muted/40 p-4 font-mono text-sm whitespace-pre-wrap">
            {baseText ?? 'No base resume saved.'}
          </pre>
        </div>
        <div className="space-y-2">
          <Label htmlFor={`draft-${resume.id}`}>Draft (you can edit this)</Label>
          <Textarea
            id={`draft-${resume.id}`}
            value={text}
            onChange={(event) => setText(event.target.value)}
            disabled={busy}
            className="h-96 overflow-auto font-mono text-sm"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => onSave(text)} disabled={busy || !unsaved}>
          Save edits
        </Button>
        <Button variant="outline" onClick={() => onDecide('reject', null)} disabled={busy}>
          Reject
        </Button>
        <Button onClick={() => onDecide('approve', unsaved ? text : null)} disabled={busy}>
          Approve
        </Button>
      </div>
    </div>
  )
}

/** Keyword coverage of the base resume, then of this resume, as the API calculated it. */
function CoverageLine({ coverage }: { coverage: ResumeCoverage }) {
  const percent = (ratio: number) => Math.round(ratio * 100)
  const list = (keywords: string[]) => (keywords.length > 0 ? keywords.join(', ') : 'none')
  return (
    <div>
      <p className="text-sm font-medium">
        {`Keyword coverage ${percent(coverage.base.ratio)}% → ${percent(coverage.ratio)}%`}
      </p>
      <p className="text-sm text-muted-foreground">
        {`Newly covered: ${list(coverage.newly_covered)}. Still missing: ${list(coverage.still_missing)}.`}
      </p>
    </div>
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
