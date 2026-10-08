import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

const RUN_POLL_MS = 3000

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
      const status = query.state.data?.status
      return status === 'PENDING' || status === 'RUNNING' ? RUN_POLL_MS : false
    },
  })
}

export function useGenerateTextRun(runIdentity: string) {
  return useQuery(generateTextRunQueryOptions(runIdentity))
}
