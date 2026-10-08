import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaDto = components['schemas']['PersonaDto']

type UpdatePersonaVariables = {
  personaIdentity: string
  persona: PersonaDto
}

async function updatePersona({ personaIdentity, persona }: UpdatePersonaVariables) {
  const { error, response } = await apiClient.PUT('/personas/{persona_identity}', {
    params: { path: { persona_identity: personaIdentity } },
    body: persona,
  })

  if (error) {
    throw createApiError(error, response)
  }
}

export function useUpdatePersona() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updatePersona,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personas'] }),
  })
}
