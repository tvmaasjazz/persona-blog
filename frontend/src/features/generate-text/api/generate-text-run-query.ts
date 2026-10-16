import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

const MAX_POLL_BACKOFF_MS = 30_000

async function findGenerateTextRun(runIdentity: string) {
  const { data, error, response } = await apiClient.GET('/generate-text/runs/{run_identity}', {
    params: { path: { run_identity: runIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function generateTextRunQueryOptions(runIdentity: string) {
  return queryOptions({
    queryKey: ['generate-text', 'runs', runIdentity],
    queryFn: () => findGenerateTextRun(runIdentity),
    refetchInterval: (query) => {
      const run = query.state.data
      if (run?.status !== 'PENDING' && run?.status !== 'RUNNING') {
        return false
      }
      // Each consecutive failed fetch doubles the wait, up to the cap.
      return Math.min(
        run.poll_interval_ms * 2 ** query.state.fetchFailureCount,
        MAX_POLL_BACKOFF_MS,
      )
    },
  })
}

export function useGenerateTextRun(runIdentity: string) {
  return useQuery(generateTextRunQueryOptions(runIdentity))
}
