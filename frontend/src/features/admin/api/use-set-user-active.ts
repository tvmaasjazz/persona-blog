import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type AdminUserActiveDto = components['schemas']['AdminUserActiveDto']

export function useSetUserActive(userIdentity: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (active: AdminUserActiveDto) => {
      const { error, response } = await apiClient.PUT('/admin/users/{user_identity}/active', {
        params: { path: { user_identity: userIdentity } },
        body: active,
      })

      if (error) {
        throw createApiError(error, response)
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}
