import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type AdminCreditGrantDto = components['schemas']['AdminCreditGrantDto']

// isOwnAccount: the signed-in admin is the target, so their balance changes too
export function useGrantUserCredits(userIdentity: string, isOwnAccount: boolean) {
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
        isOwnAccount ? queryClient.invalidateQueries({ queryKey: ['users', 'me'] }) : undefined,
      ]),
  })
}
