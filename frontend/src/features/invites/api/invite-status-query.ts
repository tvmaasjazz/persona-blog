import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findInviteStatus(inviteCode: string) {
  const { data, error, response } = await apiClient.POST('/invites/check', {
    body: { code: inviteCode },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

// The code is in the key to tell two codes apart; gcTime 0 drops it when the page unmounts.
export function inviteStatusQueryOptions(inviteCode: string) {
  return queryOptions({
    queryKey: ['invites', 'check', inviteCode],
    queryFn: () => findInviteStatus(inviteCode),
    gcTime: 0,
  })
}

export function useInviteStatus(inviteCode: string) {
  return useQuery(inviteStatusQueryOptions(inviteCode))
}
