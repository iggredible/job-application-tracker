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

/** A snapshot of the base resume is `base`; a tailored resume is `tailored`. */
export type ResumeKind = 'base' | 'tailored'

export type StepKey = 'analysis' | 'tailored' | 'apply'

export type StepStatus = 'done' | 'current' | 'available' | 'locked' | 'skipped'

/** One of the three workflow steps. The API works out the status and the line of text. */
export interface WorkflowStep {
  key: StepKey
  status: StepStatus
  text: string
}

/** The resume the application sent. */
export interface SubmittedResume {
  id: number
  kind: ResumeKind
  created_at: string
}

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
  submitted_resume: SubmittedResume | null
  applied_at: string | null
  /** Shown beside Change stage when a move from this stage happens elsewhere. */
  stage_change_hint: string | null
  steps: WorkflowStep[]
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

/** The "Resume sent" column. A display label only: the API says which resume was sent. */
export function resumeSentLabel(submitted: SubmittedResume | null): string {
  if (!submitted) return 'Not sent yet'
  return submitted.kind === 'base' ? 'Base' : 'Tailored'
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
