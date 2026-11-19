import { AIPerformanceCard } from '@/components/insights/AIPerformanceCard'
import { FunnelCard } from '@/components/insights/FunnelCard'
import { ResumeComparisonCard } from '@/components/insights/ResumeComparisonCard'
import { StatTiles } from '@/components/insights/StatTiles'
import { TimeInStageCard } from '@/components/insights/TimeInStageCard'
import { useAIMetrics, usePipelineMetrics } from '@/hooks/useMetrics'

function GroupHeading({ children }: { children: string }) {
  return (
    <h2 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
      {children}
    </h2>
  )
}

export function InsightsPage() {
  const pipeline = usePipelineMetrics()
  const ai = useAIMetrics()

  return (
    // `minmax(0,1fr)` on every grid that holds the wide table: a plain grid column is as wide as its
    // widest content, which would stretch the page instead of letting the table scroll.
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Insights</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Calculated on request from the timeline and the AI call log. Nothing here is a stored
          number.
        </p>
      </div>

      <section className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <GroupHeading>Job search</GroupHeading>
        <StatTiles query={pipeline} />
        <div className="grid gap-4 lg:grid-cols-5">
          <FunnelCard query={pipeline} />
          <TimeInStageCard query={pipeline} />
        </div>
        <ResumeComparisonCard query={pipeline} />
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <GroupHeading>AI performance</GroupHeading>
        <AIPerformanceCard query={ai} />
      </section>
    </div>
  )
}
