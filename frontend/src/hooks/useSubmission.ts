import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { detailKey, listRoot, timelineKey } from '@/hooks/useApplications'
import { api, ApiError } from '@/lib/api'
import type { Application } from '@/lib/applications'
import type { ApplyInput, SubmittableResume } from '@/lib/submission'

// Under the application's detail key, so anything that refreshes the application refreshes this.
const submittableKey = (applicationId: number) =>
  [...detailKey(applicationId), 'submittable-resumes'] as const

/**
 * What changed the application's steps or the resumes it can send (an analysis or a tailored
 * resume was approved, a draft was made). Refetches the application, which carries the steps,
 * and the options for "Which resume did you send?". Only the detail itself, not every query
 * under it: the callers refresh the rest of what they changed.
 */
export function refreshSteps(queryClient: QueryClient, applicationId: number) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: detailKey(applicationId), exact: true }),
    queryClient.invalidateQueries({ queryKey: submittableKey(applicationId) }),
  ])
}

/** The resumes the user can pick from. Only asked for while the section is open. */
export function useSubmittableResumes(applicationId: number, enabled: boolean) {
  return useQuery({
    queryKey: submittableKey(applicationId),
    queryFn: () => api<SubmittableResume[]>(`/applications/${applicationId}/submittable-resumes`),
    enabled,
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  })
}

/** Saved -> Applied with the chosen resume. The only way to apply. */
export function useApply(applicationId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ApplyInput) =>
      api<Application>(`/applications/${applicationId}/apply`, { method: 'POST', body: input }),
    onSuccess: (application) => {
      queryClient.setQueryData(detailKey(applicationId), application)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: timelineKey(applicationId) }),
        queryClient.invalidateQueries({ queryKey: submittableKey(applicationId) }),
        queryClient.invalidateQueries({ queryKey: listRoot }),
      ])
    },
    // A refused apply usually means the page was out of date (a resume changed, or the
    // application moved on), so reload what the section shows.
    onError: () => refreshSteps(queryClient, applicationId),
  })
}
