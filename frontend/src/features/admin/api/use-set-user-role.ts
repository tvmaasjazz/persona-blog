import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type AdminUserRoleDto = components['schemas']['AdminUserRoleDto']

export function useSetUserRole(userIdentity: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (role: AdminUserRoleDto) => {
      const { error, response } = await apiClient.PUT('/admin/users/{user_identity}/role', {
        params: { path: { user_identity: userIdentity } },
        body: role,
      })

      if (error) {
        throw createApiError(error, response)
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })
}
