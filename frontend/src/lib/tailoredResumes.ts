import type { ReviewStatus } from '@/lib/analysis'

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
}
