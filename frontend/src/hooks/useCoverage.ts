import { useQuery } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import type { Coverage } from '@/lib/coverage'

// Everything that changes the numbers invalidates under this key (see useAnalysis, useResume).
export const coverageKey = ['coverage'] as const

/**
 * Coverage of the base resume against the analysis the API picks, or null when the API has
 * nothing to measure (no analysis to use). Only asked for once there is a base resume to measure.
 */
export function useCoverage(applicationId: number, enabled: boolean) {
  return useQuery({
    queryKey: [...coverageKey, applicationId],
    enabled,
    queryFn: async () => {
      try {
        return await api<Coverage>(`/applications/${applicationId}/coverage`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}
