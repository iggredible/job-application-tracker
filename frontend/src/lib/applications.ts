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

export function stageLabel(stage: Stage): string {
  return stage.charAt(0).toUpperCase() + stage.slice(1)
}

export function formatAdded(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
