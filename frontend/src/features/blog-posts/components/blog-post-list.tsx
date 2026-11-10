import type { ReactNode } from 'react'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { QueryErrorState } from '@/components/query-error-state'
import { BlogPostCard } from '@/features/blog-posts/components/blog-post-card'
import type { components } from '@/lib/api-schema.gen'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']

type BlogPostListProps = {
  blogPosts: BlogPostSummaryResponseDto[] | undefined
  isPending: boolean
  error: Error | null
  // A search or filter is narrowing the list
  isNarrowed: boolean
  // Titles and status only, for a sidebar
  isCompact?: boolean
  emptyState: ReactNode
}

export function BlogPostList({
  blogPosts,
  isPending,
  error,
  isNarrowed,
  isCompact = false,
  emptyState,
}: BlogPostListProps) {
  if (isPending) {
    return <CardListSkeleton />
  }

  if (error || !blogPosts) {
    return (
      <QueryErrorState
        error={error ?? new Error('Posts not loaded')}
        notFoundMessage="Posts not found."
      />
    )
  }

  // Nothing matched, or nothing exists
  if (blogPosts.length === 0) {
    return isNarrowed ? (
      <p className="text-muted-foreground">No posts match your search or filter.</p>
    ) : (
      emptyState
    )
  }

  // One card per post
  return (
    <div className="flex flex-col gap-3">
      {blogPosts.map((blogPost) => (
        <BlogPostCard key={blogPost.identity} blogPost={blogPost} isCompact={isCompact} />
      ))}
    </div>
  )
}
