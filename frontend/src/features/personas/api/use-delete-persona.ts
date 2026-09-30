import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function deletePersona(personaIdentity: string) {
  const { error, response } = await apiClient.DELETE('/personas/{persona_identity}', {
    params: { path: { persona_identity: personaIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }
}

export function useDeletePersona() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deletePersona,
    onSuccess: (_result, personaIdentity) => {
      queryClient.removeQueries({ queryKey: ['personas', personaIdentity] })
      return queryClient.invalidateQueries({ queryKey: ['personas'], exact: true })
    },
  })
}
