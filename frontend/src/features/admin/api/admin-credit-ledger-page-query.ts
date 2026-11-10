import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

type AdminCreditLedgerPageParams = NonNullable<
  paths['/admin/users/{user_identity}/credit-ledger']['get']['parameters']['query']
>

async function findAdminCreditLedgerPage(
  userIdentity: string,
  params: AdminCreditLedgerPageParams,
) {
  const { data, error, response } = await apiClient.GET(
    '/admin/users/{user_identity}/credit-ledger',
    { params: { path: { user_identity: userIdentity }, query: params } },
  )

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function adminCreditLedgerPageQueryOptions(
  userIdentity: string,
  params: AdminCreditLedgerPageParams,
) {
  return queryOptions({
    queryKey: ['admin', 'users', userIdentity, 'credit-ledger', params],
    queryFn: () => findAdminCreditLedgerPage(userIdentity, params),
  })
}

export function useAdminCreditLedgerPage(
  userIdentity: string,
  params: AdminCreditLedgerPageParams,
  // False when the user lacks CREDIT_READ, so nothing is requested
  isEnabled: boolean,
) {
  return useQuery({
    ...adminCreditLedgerPageQueryOptions(userIdentity, params),
    enabled: isEnabled,
    placeholderData: keepPreviousData,
  })
}
