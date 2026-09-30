import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findPersonaList() {
  const { data, error, response } = await apiClient.GET('/personas')

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export const personaListQueryOptions = queryOptions({
  queryKey: ['personas'],
  queryFn: findPersonaList,
})

export function usePersonaList() {
  return useQuery(personaListQueryOptions)
}
