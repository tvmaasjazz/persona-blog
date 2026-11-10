import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type AdminCreditGrantDto = components['schemas']['AdminCreditGrantDto']

// Also refetches the signed-in user, since the target may be the admin's own account
export function useGrantUserCredits(userIdentity: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (grant: AdminCreditGrantDto) => {
      const { error, response } = await apiClient.POST(
        '/admin/users/{user_identity}/credit-grants',
        { params: { path: { user_identity: userIdentity } }, body: grant },
      )

      if (error) {
        throw createApiError(error, response)
      }
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
        queryClient.invalidateQueries({ queryKey: ['users', 'me'] }),
      ]),
  })
}
