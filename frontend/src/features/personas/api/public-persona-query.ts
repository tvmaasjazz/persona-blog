import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findPublicPersona(personaIdentity: string) {
  const { data, error, response } = await apiClient.GET('/personas/{persona_identity}/public', {
    params: { path: { persona_identity: personaIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function publicPersonaQueryOptions(personaIdentity: string) {
  return queryOptions({
    queryKey: ['personas', personaIdentity, 'public'],
    queryFn: () => findPublicPersona(personaIdentity),
  })
}

export function usePublicPersona(personaIdentity: string) {
  return useQuery(publicPersonaQueryOptions(personaIdentity))
}
