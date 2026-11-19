import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { AIMetrics, PipelineMetrics } from '@/lib/metrics'

// The API calculates both on every request, so the page asks again each time it opens (the
// default staleTime of 0) and nothing else needs to invalidate them.
export function usePipelineMetrics() {
  return useQuery({
    queryKey: ['metrics', 'pipeline'],
    queryFn: () => api<PipelineMetrics>('/metrics/pipeline'),
  })
}

export function useAIMetrics() {
  return useQuery({
    queryKey: ['metrics', 'ai'],
    queryFn: () => api<AIMetrics>('/metrics/ai'),
  })
}
