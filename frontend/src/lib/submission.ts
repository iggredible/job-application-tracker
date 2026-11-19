import type { ReviewStatus } from '@/lib/analysis'
import type { ResumeKind } from '@/lib/applications'

/** One option of "Which resume did you send?", as GET /applications/{id}/submittable-resumes
 * returns it. An option that cannot be sent is still listed, with the API's reason. */
export interface SubmittableResume {
  id: number
  kind: ResumeKind
  status: ReviewStatus
  /** When the base resume was last saved, or the tailored resume was decided (or made). */
  date: string
  submittable: boolean
  reason: string | null
}

/** The body of POST /applications/{id}/apply. */
export type ApplyInput = { choice: 'base' } | { choice: 'tailored'; resume_id: number }
