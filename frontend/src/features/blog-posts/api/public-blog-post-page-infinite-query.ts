import { keepPreviousData, queryOptions, useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components, paths } from '@/lib/api-schema.gen'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']
type PublicBlogPostPageQuery = NonNullable<
  paths['/blog-posts/public']['get']['parameters']['query']
>

export type PublicBlogPostPageInfiniteParams = Omit<PublicBlogPostPageQuery, 'page'>

async function findPublicBlogPostPage(params: PublicBlogPostPageQuery) {
  const { data, error, response } = await apiClient.GET('/blog-posts/public', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

// A read can move a post across a page boundary, so a post seen twice is kept once
function flattenPages(pages: { blog_posts: BlogPostSummaryResponseDto[] }[]) {
  const blogPostsByIdentity = new Map<string, BlogPostSummaryResponseDto>()
  for (const page of pages) {
    for (const blogPost of page.blog_posts) {
      if (!blogPostsByIdentity.has(blogPost.identity)) {
        blogPostsByIdentity.set(blogPost.identity, blogPost)
      }
    }
  }
  return [...blogPostsByIdentity.values()]
}

// The key ends in 'infinite' because infinite data is pages, not a page
export function usePublicBlogPostPageInfinite(params: PublicBlogPostPageInfiniteParams) {
  return useInfiniteQuery({
    queryKey: ['blog-posts', 'public', params, 'infinite'],
    queryFn: ({ pageParam }) => findPublicBlogPostPage({ ...params, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: ({ pagination }) =>
      pagination.page * pagination.page_size < pagination.total ? pagination.page + 1 : undefined,
    select: (data) => flattenPages(data.pages),
  })
}

export function usePublicBlogPostCount(personaIdentity: string) {
  const params = { persona_identity: personaIdentity, page_size: 1 }

  return useQuery(
    queryOptions({
      queryKey: ['blog-posts', 'public', params],
      queryFn: () => findPublicBlogPostPage(params),
      select: (data) => data.pagination.total,
      placeholderData: keepPreviousData,
    }),
  )
}
