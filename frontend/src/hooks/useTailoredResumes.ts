import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import type { TailoredResume } from '@/lib/tailoredResumes'

// Under the application's detail key, so anything that refreshes the application refreshes this.
const tailoredKey = (applicationId: number) =>
  ['applications', applicationId, 'tailored-resumes'] as const

/** The application's tailored resumes, newest first. */
export function useTailoredResumes(applicationId: number) {
  return useQuery({
    queryKey: tailoredKey(applicationId),
    queryFn: () => api<TailoredResume[]>(`/applications/${applicationId}/tailored-resumes`),
    // A missing application will not appear by retrying.
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  })
}

/** Makes the AI call. The list is refetched once the new draft is saved. */
export function useTailorResume(applicationId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api<TailoredResume>(`/applications/${applicationId}/tailored-resumes`, {
        method: 'POST',
        body: undefined,
      }),
    // Returned, so the buttons stay disabled until the section shows the new draft.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tailoredKey(applicationId) }),
  })
}
