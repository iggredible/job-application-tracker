import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useCoverage } from '@/hooks/useCoverage'
import { useResume } from '@/hooks/useResume'

function KeywordList({
  label,
  keywords,
  missing = false,
}: {
  label: string
  keywords: string[]
  missing?: boolean
}) {
  if (keywords.length === 0) return null
  return (
    <div className="grid gap-1.5">
      <h4 className="text-xs text-muted-foreground">{label}</h4>
      <ul aria-label={`${label} keywords`} className="flex flex-wrap gap-1.5">
        {keywords.map((keyword) => (
          <li key={keyword}>
            <Badge
              variant={missing ? 'outline' : 'secondary'}
              className={missing ? 'border-dashed' : undefined}
            >
              {keyword}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Which of the analysis keywords the base resume contains. The API calculates it on every
 * request; this only draws it. With no base resume there is nothing to measure, so it links to
 * the Resume page instead. It shows nothing when the API has no analysis to measure. */
export function CoverageBlock({ applicationId }: { applicationId: number }) {
  const { data: resume, isPending: resumePending } = useResume()
  const hasResume = !resumePending && resume !== null && resume !== undefined
  const { data: coverage } = useCoverage(applicationId, hasResume)

  if (resumePending) return null

  if (!hasResume) {
    return (
      <section aria-label="Keyword coverage" className="grid gap-2 border-t pt-4">
        <h3 className="text-sm font-medium">Keyword coverage, base resume</h3>
        <p className="text-sm text-muted-foreground">
          Add your base resume on the{' '}
          <Link to="/resume" className="underline">
            Resume page
          </Link>{' '}
          to see which keywords it covers.
        </p>
      </section>
    )
  }

  const total = coverage ? coverage.covered.length + coverage.missing.length : 0
  if (!coverage || total === 0) return null

  const percent = Math.round(coverage.ratio * 100)
  return (
    <section aria-label="Keyword coverage" className="grid gap-3 border-t pt-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">Keyword coverage, base resume</h3>
        <p className="text-sm">
          <span className="font-semibold">{percent}%</span>{' '}
          <span className="text-muted-foreground">
            {`(${coverage.covered.length} of ${total})`}
          </span>
        </p>
      </div>
      <Progress
        value={percent}
        className="h-2"
        aria-label="Keyword coverage, base resume"
      />
      <KeywordList label="Covered" keywords={coverage.covered} />
      <KeywordList label="Missing" keywords={coverage.missing} missing />
    </section>
  )
}
