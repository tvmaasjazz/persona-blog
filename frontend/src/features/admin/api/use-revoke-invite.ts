import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

export function useRevokeInvite() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (inviteIdentity: string) => {
      const { error, response } = await apiClient.POST('/admin/invites/{invite_identity}/revoke', {
        params: { path: { invite_identity: inviteIdentity } },
      })

      if (error) {
        throw createApiError(error, response)
      }
    },
    // Settles on failure too, since a 409 means the table shows a stale status
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['admin', 'invites'] }),
  })
}
