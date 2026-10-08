import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findBlogPost(blogPostIdentity: string) {
  const { data, error, response } = await apiClient.GET('/blog-posts/{blog_post_identity}', {
    params: { path: { blog_post_identity: blogPostIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function blogPostQueryOptions(blogPostIdentity: string) {
  return queryOptions({
    queryKey: ['blog-posts', blogPostIdentity],
    queryFn: () => findBlogPost(blogPostIdentity),
  })
}

export function useBlogPost(blogPostIdentity: string) {
  return useQuery(blogPostQueryOptions(blogPostIdentity))
}
