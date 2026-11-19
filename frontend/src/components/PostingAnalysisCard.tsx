import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { CoverageBlock } from '@/components/CoverageBlock'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAnalysis, useReviewAnalysis, useRunAnalysis } from '@/hooks/useAnalysis'
import type { PostingAnalysis, Requirement, ReviewStatus } from '@/lib/analysis'
import { formatDay } from '@/lib/applications'

const badgeVariant: Record<ReviewStatus, 'outline' | 'default' | 'destructive'> = {
  draft: 'outline',
  approved: 'default',
  rejected: 'destructive',
}

const badgeLabel: Record<ReviewStatus, string> = {
  draft: 'Draft',
  approved: 'Approved',
  rejected: 'Rejected',
}

function RequirementList({
  title,
  category,
  requirements,
}: {
  title: string
  category: Requirement['category']
  requirements: Requirement[]
}) {
  const items = requirements.filter((r) => r.category === category)
  return (
    <div className="grid content-start gap-2">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None</p>
      ) : (
        <ul aria-label={title} className="grid list-disc gap-1.5 pl-5 text-sm">
          {items.map((requirement, index) => (
            <li key={index}>{requirement.text}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AnalysisBody({ analysis }: { analysis: PostingAnalysis }) {
  return (
    <>
      <div className="grid gap-6 sm:grid-cols-2">
        <RequirementList
          title="Must have"
          category="must_have"
          requirements={analysis.requirements}
        />
        <RequirementList
          title="Nice to have"
          category="nice_to_have"
          requirements={analysis.requirements}
        />
      </div>
      <div className="grid gap-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Keywords
        </h3>
        {analysis.keywords.length === 0 ? (
          <p className="text-sm text-muted-foreground">None</p>
        ) : (
          <ul aria-label="Keywords" className="flex flex-wrap gap-1.5">
            {analysis.keywords.map((keyword) => (
              <li key={keyword}>
                <Badge variant="secondary">{keyword}</Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

/** The posting analysis: empty, draft (to review), approved or rejected. The API picks which
 * analysis to show; the card renders the buttons for its status (Reject and Approve on a draft,
 * Analyze again on any), as the spec's four states describe. */
export function PostingAnalysisCard({ applicationId }: { applicationId: number }) {
  const { data: analysis, isPending, isError } = useAnalysis(applicationId)
  const run = useRunAnalysis(applicationId)
  const review = useReviewAnalysis(applicationId)
  const busy = run.isPending || review.isPending

  function analyze() {
    run.mutate(undefined, {
      onError: (error) => toast.error(error.message || 'The analysis failed. Try again.'),
    })
  }

  function decide(analysisId: number, decision: 'approve' | 'reject') {
    review.mutate(
      { analysisId, decision },
      { onError: (error) => toast.error(error.message || `Could not ${decision} the analysis`) },
    )
  }

  const analyzeLabel = (idle: string) =>
    run.isPending ? (
      <>
        <Loader2 className="animate-spin" aria-hidden="true" />
        Analyzing…
      </>
    ) : (
      idle
    )

  return (
    <section aria-label="Posting analysis" aria-busy={run.isPending}>
      <Card className="h-full">
        <CardHeader className="flex flex-row flex-wrap items-center gap-2">
          <CardTitle className="text-lg">Posting analysis</CardTitle>
          {analysis && (
            <>
              <Badge variant={badgeVariant[analysis.status]}>{badgeLabel[analysis.status]}</Badge>
              <span className="text-sm text-muted-foreground">
                {`Prompt ${analysis.prompt_version} · Generated ${formatDay(analysis.created_at)}`}
              </span>
            </>
          )}
        </CardHeader>
        <CardContent className="grid gap-5">
          {isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">Could not load the analysis.</p>}

          {analysis === null && (
            <>
              <p className="text-sm">No analysis yet</p>
              <p className="text-sm text-muted-foreground">
                Analyze reads the job posting and lists what it asks for. You review the result
                before anything uses it.
              </p>
              <div>
                <Button onClick={analyze} disabled={busy}>
                  {analyzeLabel('Analyze')}
                </Button>
              </div>
            </>
          )}

          {analysis && (
            <>
              <AnalysisBody analysis={analysis} />
              <CoverageBlock applicationId={analysis.application_id} />
              {analysis.status === 'draft' && (
                <p className="border-t pt-4 text-sm text-muted-foreground">
                  Check that the requirements and keywords match the posting. Tailoring uses the
                  approved keywords.
                </p>
              )}
              {analysis.status === 'rejected' && (
                <p className="border-t pt-4 text-sm text-muted-foreground">
                  You rejected this analysis. Analyze again to get a new draft.
                </p>
              )}
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={analyze} disabled={busy}>
                  {analyzeLabel('Analyze again')}
                </Button>
                {analysis.status === 'draft' && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => decide(analysis.id, 'reject')}
                      disabled={busy}
                    >
                      Reject
                    </Button>
                    <Button onClick={() => decide(analysis.id, 'approve')} disabled={busy}>
                      Approve
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
