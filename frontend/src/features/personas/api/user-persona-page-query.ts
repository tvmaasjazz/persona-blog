import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

type UserPersonaPageParams = NonNullable<paths['/personas']['get']['parameters']['query']>

const PERSONA_OPTIONS_LIMIT = 100

async function findUserPersonaPage(params: UserPersonaPageParams) {
  const { data, error, response } = await apiClient.GET('/personas', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function userPersonaPageQueryOptions(params: UserPersonaPageParams) {
  return queryOptions({
    queryKey: ['personas', params],
    queryFn: () => findUserPersonaPage(params),
  })
}

export function useUserPersonaPage(params: UserPersonaPageParams) {
  return useQuery({ ...userPersonaPageQueryOptions(params), placeholderData: keepPreviousData })
}

// The first 100 personas by name, for selects and filters
export function usePersonaOptions() {
  return useQuery({
    ...userPersonaPageQueryOptions({
      page: 1,
      page_size: PERSONA_OPTIONS_LIMIT,
      sort_by: 'NAME',
      sort_direction: 'ASC',
    }),
    select: (page) => page.personas,
  })
}
