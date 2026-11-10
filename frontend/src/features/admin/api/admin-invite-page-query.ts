import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

type AdminInvitePageParams = NonNullable<paths['/admin/invites']['get']['parameters']['query']>

async function findAdminInvitePage(params: AdminInvitePageParams) {
  const { data, error, response } = await apiClient.GET('/admin/invites', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function adminInvitePageQueryOptions(params: AdminInvitePageParams) {
  return queryOptions({
    queryKey: ['admin', 'invites', params],
    queryFn: () => findAdminInvitePage(params),
  })
}

export function useAdminInvitePage(params: AdminInvitePageParams) {
  return useQuery({ ...adminInvitePageQueryOptions(params), placeholderData: keepPreviousData })
}
