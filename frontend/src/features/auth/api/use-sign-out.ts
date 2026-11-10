import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import { resetQueriesExceptCurrentUser } from '@/lib/reset-queries-except-current-user'

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
      // An open page's answer depends on who asked (is_owner, an owner's private record),
      // so everything else cached is reset and an open page refetches signed out
      resetQueriesExceptCurrentUser(queryClient)
    },
  })
}
