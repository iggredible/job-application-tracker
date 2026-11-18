import { Badge } from '@/components/ui/badge'
import { stageLabel, type Stage } from '@/lib/applications'

const variants: Record<Stage, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  saved: 'secondary',
  applied: 'secondary',
  screening: 'secondary',
  interviewing: 'secondary',
  offer: 'secondary',
  accepted: 'default',
  rejected: 'destructive',
  withdrawn: 'outline',
}

export function StageBadge({ stage }: { stage: Stage }) {
  return <Badge variant={variants[stage]}>{stageLabel(stage)}</Badge>
}
