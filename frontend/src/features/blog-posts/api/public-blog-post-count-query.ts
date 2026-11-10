import { queryOptions, useQuery } from '@tanstack/react-query'

import { findPublicBlogPostPage } from '@/features/blog-posts/api/public-blog-post-page-query'

// The page route with page_size=1, read for its total
export function publicBlogPostCountQueryOptions(personaIdentity: string) {
  const params = { persona_identity: personaIdentity, page_size: 1 }

  return queryOptions({
    queryKey: ['blog-posts', 'public', params],
    queryFn: () => findPublicBlogPostPage(params),
    select: (data) => data.pagination.total,
  })
}

export function usePublicBlogPostCount(personaIdentity: string) {
  return useQuery(publicBlogPostCountQueryOptions(personaIdentity))
}
