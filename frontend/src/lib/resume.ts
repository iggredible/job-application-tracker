export interface Resume {
  id: number
  content_markdown: string
  status: 'draft' | 'approved' | 'rejected'
  created_at: string
  updated_at: string
  reviewed_at: string | null
}
