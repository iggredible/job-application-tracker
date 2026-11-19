import type { ReviewStatus } from '@/lib/analysis'
import type { ResumeCoverage } from '@/lib/coverage'

/** A fact in the draft that the base resume does not support. `message` is shown as is. */
export interface GuardrailFlag {
  field: string
  value: string
  message: string
}

/** One tailored resume, as GET /applications/{id}/tailored-resumes returns it (newest first). */
export interface TailoredResume {
  id: number
  application_id: number
  status: ReviewStatus
  prompt_version: string
  content_markdown: string
  /** The current flags: they follow the text as it is now. */
  guardrail_flags: GuardrailFlag[]
  created_at: string
  reviewed_at: string | null
  /** What became of the resume, worked out by the API. */
  outcome: ResumeOutcome
  /** The API marks one resume per application as the one the section shows. */
  displayed: boolean
}

export type ResumeOutcome =
  | 'pending'
  | 'superseded'
  | 'approved'
  | 'edited_then_approved'
  | 'rejected'

/** The answer to PATCH /resumes/{id}: the resume with its current flags, and the coverage of
 * its new text. */
export interface SavedResume extends TailoredResume {
  coverage: ResumeCoverage
}
