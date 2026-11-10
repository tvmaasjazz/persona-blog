import { queryOptions, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function findPublicBlogPost(blogPostIdentity: string) {
  const { data, error, response } = await apiClient.GET('/blog-posts/{blog_post_identity}/public', {
    params: { path: { blog_post_identity: blogPostIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function publicBlogPostQueryOptions(blogPostIdentity: string) {
  return queryOptions({
    queryKey: ['blog-posts', blogPostIdentity, 'public'],
    queryFn: () => findPublicBlogPost(blogPostIdentity),
  })
}

export function usePublicBlogPost(blogPostIdentity: string) {
  return useQuery(publicBlogPostQueryOptions(blogPostIdentity))
}
