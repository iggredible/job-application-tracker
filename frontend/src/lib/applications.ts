export type Source = 'referral' | 'linkedin' | 'company_site' | 'recruiter' | 'other'

export type Stage =
  | 'saved'
  | 'applied'
  | 'screening'
  | 'interviewing'
  | 'offer'
  | 'accepted'
  | 'rejected'
  | 'withdrawn'

export interface Application {
  id: number
  company: string
  role: string
  source: Source
  stage: Stage
  posting_url: string | null
  posting_text: string
  created_at: string
  updated_at: string
  // Calculated by the API on every request. The page only displays them.
  allowed_next_stages: Stage[]
  last_activity_at: string
  is_stale: boolean
  idle_days: number
}

/** GET /applications. The counts and the stale count cover every application, filtered or not. */
export interface ApplicationList {
  items: Application[]
  counts_by_stage: Record<Stage, number>
  stale_count: number
}

export interface TimelineEvent {
  id: number
  application_id: number
  type: 'stage_change' | 'note'
  from_stage: Stage | null
  to_stage: Stage | null
  note: string | null
  created_at: string
}

/** The five fields the API lets a user set. `stage` is not one of them. */
export interface ApplicationInput {
  company: string
  role: string
  source: Source
  posting_url: string | null
  posting_text: string
}

// Display labels only. The backend enum is the source of truth for the values.
export const SOURCES: { value: Source; label: string }[] = [
  { value: 'referral', label: 'Referral' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'company_site', label: 'Company site' },
  { value: 'recruiter', label: 'Recruiter' },
  { value: 'other', label: 'Other' },
]

export function sourceLabel(source: Source): string {
  return SOURCES.find((s) => s.value === source)?.label ?? source
}

// Display order for the filter pills. Which moves are allowed comes from the API.
export const STAGES: Stage[] = [
  'saved',
  'applied',
  'screening',
  'interviewing',
  'offer',
  'accepted',
  'rejected',
  'withdrawn',
]

export function isStage(value: string | null): value is Stage {
  return STAGES.some((s) => s === value)
}

export function stageLabel(stage: Stage): string {
  return stage.charAt(0).toUpperCase() + stage.slice(1)
}

export function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}
