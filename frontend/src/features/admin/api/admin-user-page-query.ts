import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

type AdminUserPageParams = NonNullable<paths['/admin/users']['get']['parameters']['query']>

async function findAdminUserPage(params: AdminUserPageParams) {
  const { data, error, response } = await apiClient.GET('/admin/users', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function adminUserPageQueryOptions(params: AdminUserPageParams) {
  return queryOptions({
    queryKey: ['admin', 'users', params],
    queryFn: () => findAdminUserPage(params),
  })
}

export function useAdminUserPage(params: AdminUserPageParams) {
  return useQuery({ ...adminUserPageQueryOptions(params), placeholderData: keepPreviousData })
}
