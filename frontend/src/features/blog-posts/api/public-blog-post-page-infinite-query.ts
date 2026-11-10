import { infiniteQueryOptions, keepPreviousData, useInfiniteQuery } from '@tanstack/react-query'
import type { InfiniteData } from '@tanstack/react-query'

import {
  findPublicBlogPostPage,
  type PublicBlogPostPageQuery,
} from '@/features/blog-posts/api/public-blog-post-page-query'
import type { components } from '@/lib/api-schema.gen'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']
type PublicBlogPostPageResponseDto = components['schemas']['PublicBlogPostPageResponseDto']

export type PublicBlogPostPageInfiniteParams = Omit<PublicBlogPostPageQuery, 'page'>

// A read can move a post across a page boundary, so a post seen twice is kept once
function flattenPages(data: InfiniteData<PublicBlogPostPageResponseDto, number>) {
  const blogPostsByIdentity = new Map<string, BlogPostSummaryResponseDto>()
  for (const page of data.pages) {
    for (const blogPost of page.blog_posts) {
      if (!blogPostsByIdentity.has(blogPost.identity)) {
        blogPostsByIdentity.set(blogPost.identity, blogPost)
      }
    }
  }
  return [...blogPostsByIdentity.values()]
}

// The key ends in 'infinite' because infinite data is pages, not a page
export function publicBlogPostPageInfiniteQueryOptions(params: PublicBlogPostPageInfiniteParams) {
  return infiniteQueryOptions({
    queryKey: ['blog-posts', 'public', params, 'infinite'],
    queryFn: ({ pageParam }) => findPublicBlogPostPage({ ...params, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: ({ pagination }) =>
      pagination.page * pagination.page_size < pagination.total ? pagination.page + 1 : undefined,
    // A new search keeps the old posts on screen until its first page arrives
    placeholderData: keepPreviousData,
    select: flattenPages,
  })
}

export function usePublicBlogPostPageInfinite(params: PublicBlogPostPageInfiniteParams) {
  return useInfiniteQuery(publicBlogPostPageInfiniteQueryOptions(params))
}
