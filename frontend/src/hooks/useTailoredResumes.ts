import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { coverageKey, resumeCoverageKey } from '@/hooks/useCoverage'
import { api, ApiError } from '@/lib/api'
import type { SavedResume, TailoredResume } from '@/lib/tailoredResumes'

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

/** Saves the edited text. The response has the new flags and coverage, so they are put where the
 * section reads them, and nothing is refetched. They change on save, never while typing. */
export function useSaveEdits(applicationId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ resumeId, text }: { resumeId: number; text: string }) =>
      api<SavedResume>(`/resumes/${resumeId}`, {
        method: 'PATCH',
        body: { content_markdown: text },
      }),
    onSuccess: ({ coverage, ...saved }) => {
      queryClient.setQueryData<TailoredResume[]>(tailoredKey(applicationId), (list) =>
        list?.map((resume) => (resume.id === saved.id ? saved : resume)),
      )
      queryClient.setQueryData(resumeCoverageKey(applicationId, saved.id), coverage)
    },
    // A refused save usually means the page was out of date, so reload what it shows.
    onError: () => queryClient.invalidateQueries({ queryKey: tailoredKey(applicationId) }),
  })
}

/** Approve or reject. Approving saves unsaved edits first (`unsavedText`), so the approved text
 * is the text on the screen. The list is refetched rather than set from the response, because
 * the API decides which resume is displayed afterwards. */
export function useReviewResume(applicationId: number) {
  const queryClient = useQueryClient()
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: tailoredKey(applicationId) }),
      queryClient.invalidateQueries({ queryKey: coverageKey }),
    ])
  return useMutation({
    mutationFn: async ({
      resumeId,
      decision,
      unsavedText,
    }: {
      resumeId: number
      decision: 'approve' | 'reject'
      unsavedText: string | null
    }) => {
      if (decision === 'approve' && unsavedText !== null) {
        await api<SavedResume>(`/resumes/${resumeId}`, {
          method: 'PATCH',
          body: { content_markdown: unsavedText },
        })
      }
      return api<TailoredResume>(`/resumes/${resumeId}/${decision}`, {
        method: 'POST',
        body: undefined,
      })
    },
    // Returned, so the buttons stay disabled until the section shows what the API now says.
    onSuccess: () => refresh(),
    onError: () => refresh(),
  })
}
