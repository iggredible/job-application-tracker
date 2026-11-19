import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import type {
  Application,
  ApplicationInput,
  ApplicationList,
  Stage,
  TimelineEvent,
} from '@/lib/applications'

export const listRoot = ['applications', 'list'] as const
const listKey = (stage?: Stage) => [...listRoot, stage ?? 'all'] as const
// The timeline key starts with the detail key, so invalidating the detail refreshes both.
export const detailKey = (id: number) => ['applications', id] as const
export const timelineKey = (id: number) => [...detailKey(id), 'timeline'] as const

export function useApplications(stage?: Stage) {
  return useQuery({
    queryKey: listKey(stage),
    queryFn: () =>
      api<ApplicationList>(stage ? `/applications?stage=${stage}` : '/applications'),
    // Keep the pills and table on screen while another stage loads, instead of flashing empty.
    placeholderData: keepPreviousData,
  })
}

export function useApplication(id: number) {
  return useQuery({
    queryKey: detailKey(id),
    queryFn: () => api<Application>(`/applications/${id}`),
    // A missing application will not appear by retrying.
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  })
}

export function useTimeline(id: number) {
  return useQuery({
    queryKey: timelineKey(id),
    queryFn: () => api<TimelineEvent[]>(`/applications/${id}/timeline`),
  })
}

export function useCreateApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ApplicationInput) =>
      api<Application>('/applications', { method: 'POST', body: input }),
    onSuccess: (application) => {
      queryClient.setQueryData(detailKey(application.id), application)
      return queryClient.invalidateQueries({ queryKey: listRoot })
    },
  })
}

export function useUpdateApplication(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ApplicationInput) =>
      api<Application>(`/applications/${id}`, { method: 'PATCH', body: input }),
    onSuccess: (application) => {
      queryClient.setQueryData(detailKey(id), application)
      return queryClient.invalidateQueries({ queryKey: listRoot })
    },
  })
}

export function useChangeStage(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (toStage: Stage) =>
      api<Application>(`/applications/${id}/stage`, {
        method: 'POST',
        body: { to_stage: toStage },
      }),
    onSuccess: (application) => {
      queryClient.setQueryData(detailKey(id), application)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: timelineKey(id) }),
        queryClient.invalidateQueries({ queryKey: listRoot }),
      ])
    },
    // A refused move usually means the page was out of date (for example the stage changed in
    // another tab). Reload the application so the menu shows what the API allows now.
    onError: () => queryClient.invalidateQueries({ queryKey: detailKey(id) }),
  })
}

export function useAddNote(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (note: string) =>
      api<TimelineEvent>(`/applications/${id}/notes`, { method: 'POST', body: { note } }),
    // A note is activity, so the application's last activity and stale flag change too.
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: detailKey(id) }),
        queryClient.invalidateQueries({ queryKey: listRoot }),
      ]),
  })
}
