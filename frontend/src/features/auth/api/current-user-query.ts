import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { components } from '@/lib/api-schema.gen'

type UserResponseDto = components['schemas']['UserResponseDto']

async function findCurrentUser(): Promise<UserResponseDto | null> {
  const { data, error, response } = await apiClient.GET('/users/me')

  if (response.status === 401) {
    return null
  }

  if (error) {
    throw error
  }

  return data
}

export const currentUserQueryOptions = queryOptions({
  queryKey: ['users', 'me'],
  queryFn: findCurrentUser,
})

export function useCurrentUser() {
  return useQuery(currentUserQueryOptions)
}
