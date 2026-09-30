import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findPersona(personaIdentity: string) {
  const { data, error, response } = await apiClient.GET('/personas/{persona_identity}', {
    params: { path: { persona_identity: personaIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function personaQueryOptions(personaIdentity: string) {
  return queryOptions({
    queryKey: ['personas', personaIdentity],
    queryFn: () => findPersona(personaIdentity),
  })
}

export function usePersona(personaIdentity: string) {
  return useQuery(personaQueryOptions(personaIdentity))
}
