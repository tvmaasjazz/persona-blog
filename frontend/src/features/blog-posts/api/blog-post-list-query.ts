import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findBlogPostList(personaIdentity?: string) {
  const { data, error, response } = await apiClient.GET('/blog-posts', {
    params: { query: { persona_identity: personaIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function blogPostListQueryOptions(personaIdentity?: string) {
  return queryOptions({
    queryKey: personaIdentity ? ['blog-posts', { personaIdentity }] : ['blog-posts'],
    queryFn: () => findBlogPostList(personaIdentity),
  })
}

export function useBlogPostList(personaIdentity?: string) {
  return useQuery(blogPostListQueryOptions(personaIdentity))
}
