import type { UseQueryResult } from '@tanstack/react-query'
import { Bar, BarChart, LabelList, XAxis, YAxis } from 'recharts'

import { InsightCard, SectionState } from '@/components/insights/SectionState'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { stageLabel } from '@/lib/applications'
import { formatPercent, type PipelineMetrics } from '@/lib/metrics'

const config = {
  count: { label: 'Applications', color: 'var(--primary)' },
} satisfies ChartConfig

interface FunnelBar {
  stage: string
  count: number
  share: number | null
}

// What recharts hands a custom label: where the bar ends and which bar it is.
interface LabelProps {
  x?: number | string
  y?: number | string
  width?: number | string
  height?: number | string
  index?: number
}

export function FunnelCard({ query }: { query: UseQueryResult<PipelineMetrics> }) {
  const data = query.data
  const bars: FunnelBar[] =(data?.funnel ?? []).map((step) => ({
    stage: stageLabel(step.stage),
    count: step.count,
    share: step.share_of_previous,
  }))
  // Nothing reached Applied, so every bar would be empty.
  const empty = data && data.applied_applications === 0 ? 'No applications have reached Applied yet' : null

  function renderLabel({ x = 0, y = 0, width = 0, height = 0, index = 0 }: LabelProps) {
    const bar = bars[index]
    if (!bar) return null
    return (
      <text
        x={Number(x) + Number(width) + 8}
        y={Number(y) + Number(height) / 2}
        dominantBaseline="central"
        className="fill-foreground text-xs"
      >
        <tspan className="font-semibold">{bar.count}</tspan>
        {bar.share !== null && (
          <tspan dx={6} className="fill-muted-foreground">
            {formatPercent(bar.share)} moved on
          </tspan>
        )}
      </text>
    )
  }

  return (
    <InsightCard
      title="Funnel"
      description="Applications that reached each stage, and the share that moved on from the stage before"
      className="lg:col-span-3"
    >
      <SectionState isPending={query.isPending} isError={query.isError} empty={empty}>
        <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
          <BarChart
            accessibilityLayer
            data={bars}
            layout="vertical"
            margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
          >
            <XAxis type="number" hide domain={[0, (max: number) => Math.ceil(max * 1.5)]} />
            <YAxis
              type="category"
              dataKey="stage"
              tickLine={false}
              axisLine={false}
              width={90}
              tick={{ fontSize: 14 }}
            />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" fill="var(--color-count)" radius={4} barSize={22} isAnimationActive={false}>
              <LabelList content={renderLabel} />
            </Bar>
          </BarChart>
        </ChartContainer>
      </SectionState>
    </InsightCard>
  )
}
