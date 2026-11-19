import type { ReviewStatus } from '@/lib/analysis'

/** One tailored resume, as GET /applications/{id}/tailored-resumes returns it (newest first). */
export interface TailoredResume {
  id: number
  application_id: number
  status: ReviewStatus
  prompt_version: string
  content_markdown: string
  created_at: string
}
