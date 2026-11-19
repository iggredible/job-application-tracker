import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import type { Application, ApplicationInput } from '@/lib/applications'

const listKey = ['applications'] as const
const detailKey = (id: number) => ['applications', id] as const

export function useApplications() {
  return useQuery({
    queryKey: listKey,
    queryFn: () => api<Application[]>('/applications'),
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

export function useCreateApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ApplicationInput) =>
      api<Application>('/applications', { method: 'POST', body: input }),
    onSuccess: (application) => {
      queryClient.setQueryData(detailKey(application.id), application)
      return queryClient.invalidateQueries({ queryKey: listKey, exact: true })
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
      return queryClient.invalidateQueries({ queryKey: listKey, exact: true })
    },
  })
}
