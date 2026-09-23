import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'

async function signOut(): Promise<void> {
  const { error } = await apiClient.POST('/auth/logout')

  if (error) {
    throw error
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
