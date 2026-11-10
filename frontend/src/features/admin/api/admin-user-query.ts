import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findAdminUser(userIdentity: string) {
  const { data, error, response } = await apiClient.GET('/admin/users/{user_identity}', {
    params: { path: { user_identity: userIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function adminUserQueryOptions(userIdentity: string) {
  return queryOptions({
    queryKey: ['admin', 'users', userIdentity],
    queryFn: () => findAdminUser(userIdentity),
  })
}

export function useAdminUser(userIdentity: string) {
  return useQuery(adminUserQueryOptions(userIdentity))
}
