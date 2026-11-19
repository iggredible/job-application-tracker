import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import type { PostingAnalysis } from '@/lib/analysis'

// Under the application's detail key, so anything that refreshes the application refreshes this.
const analysisKey = (applicationId: number) => ['applications', applicationId, 'analysis'] as const

/** The analysis to display, or null when there is none. The API decides which one. */
export function useAnalysis(applicationId: number) {
  return useQuery({
    queryKey: analysisKey(applicationId),
    queryFn: () => api<PostingAnalysis | null>(`/applications/${applicationId}/analysis`),
    // A missing application will not appear by retrying.
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  })
}

/** Makes the AI call. The API answers with the new draft once it is saved. */
export function useRunAnalysis(applicationId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api<PostingAnalysis>(`/applications/${applicationId}/analysis`, {
        method: 'POST',
        body: undefined,
      }),
    onSuccess: (analysis) => queryClient.setQueryData(analysisKey(applicationId), analysis),
  })
}

/** Approve or reject. The card is refetched rather than set from the response, because after a
 * rejection the API may want an older approved analysis shown instead. */
export function useReviewAnalysis(applicationId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ analysisId, decision }: { analysisId: number; decision: 'approve' | 'reject' }) =>
      api<PostingAnalysis>(`/analyses/${analysisId}/${decision}`, {
        method: 'POST',
        body: undefined,
      }),
    // Returned, so the buttons stay disabled until the card shows what the API now says.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: analysisKey(applicationId) }),
    // A refused decision usually means the page was out of date, so reload what it shows.
    onError: () => queryClient.invalidateQueries({ queryKey: analysisKey(applicationId) }),
  })
}
