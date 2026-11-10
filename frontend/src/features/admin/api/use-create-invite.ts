import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type AdminInviteDto = components['schemas']['AdminInviteDto']

// Resolves to the invite's link, which the API never returns again
export function useCreateInvite() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (invite: AdminInviteDto) => {
      const { data, error, response } = await apiClient.POST('/admin/invites', { body: invite })

      if (error) {
        throw createApiError(error, response)
      }

      return data.invite_url
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'invites'] }),
  })
}
