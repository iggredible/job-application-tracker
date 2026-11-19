export type ReviewStatus = 'draft' | 'approved' | 'rejected'

export interface Requirement {
  text: string
  category: 'must_have' | 'nice_to_have'
}

/** What the API says the Posting analysis card should display. */
export interface PostingAnalysis {
  id: number
  application_id: number
  status: ReviewStatus
  prompt_version: string
  requirements: Requirement[]
  keywords: string[]
  created_at: string
  reviewed_at: string | null
}
