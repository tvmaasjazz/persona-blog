import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaDto = components['schemas']['PersonaDto']

async function createPersona(persona: PersonaDto): Promise<string> {
  const { data, error, response } = await apiClient.POST('/personas', { body: persona })

  if (error) {
    throw createApiError(error, response)
  }

  return data.identity
}

export function useCreatePersona() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createPersona,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personas'] }),
  })
}
