import { keepPreviousData, queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

type UserBlogPostPageParams = NonNullable<paths['/blog-posts']['get']['parameters']['query']>

async function findUserBlogPostPage(params: UserBlogPostPageParams) {
  const { data, error, response } = await apiClient.GET('/blog-posts', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function userBlogPostPageQueryOptions(params: UserBlogPostPageParams) {
  return queryOptions({
    queryKey: ['blog-posts', params],
    queryFn: () => findUserBlogPostPage(params),
  })
}

export function useUserBlogPostPage(params: UserBlogPostPageParams) {
  return useQuery({ ...userBlogPostPageQueryOptions(params), placeholderData: keepPreviousData })
}
