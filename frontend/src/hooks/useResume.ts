import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { coverageKey } from '@/hooks/useCoverage'
import { api, ApiError } from '@/lib/api'
import type { Resume } from '@/lib/resume'

const resumeKey = ['resume'] as const

/** The base resume, or null when none has been saved yet. A missing resume is a normal state. */
export function useResume() {
  return useQuery({
    queryKey: resumeKey,
    queryFn: async () => {
      try {
        return await api<Resume>('/resume')
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}

export function useSaveResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (contentMarkdown: string) =>
      api<Resume>('/resume', { method: 'PUT', body: { content_markdown: contentMarkdown } }),
    onSuccess: (resume) => {
      queryClient.setQueryData(resumeKey, resume)
      // The base resume's text is what coverage is measured against, and saving the first one
      // unlocks the Mark as applied step of every application.
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: coverageKey }),
        queryClient.invalidateQueries({ queryKey: ['applications'] }),
      ])
    },
  })
}
