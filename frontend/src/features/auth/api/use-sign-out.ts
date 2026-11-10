import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function signOut(): Promise<void> {
  const { error, response } = await apiClient.POST('/auth/logout')

  // A 401 means the session is already gone, which is what signing out wanted
  if (error && response.status !== 401) {
    throw createApiError(error, response)
  }
}

export function useSignOut() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: signOut,
    onSuccess: () => {
      queryClient.setQueryData(['users', 'me'], null)
      queryClient.invalidateQueries({ queryKey: ['users', 'me'] })
    },
  })
}
