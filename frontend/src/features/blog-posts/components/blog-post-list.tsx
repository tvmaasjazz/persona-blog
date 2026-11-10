import type { ReactNode } from 'react'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { BlogPostCard } from '@/features/blog-posts/components/blog-post-card'
import type { components } from '@/lib/api-schema.gen'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']
type PaginationResponseDto = components['schemas']['PaginationResponseDto']

type BlogPostListProps = {
  blogPosts: BlogPostSummaryResponseDto[] | undefined
  isPending: boolean
  error: Error | null
  // A search or filter is narrowing the list
  isNarrowed: boolean
  // Together these catch a page past the last one; a list fixed to page 1 omits them
  pagination?: PaginationResponseDto
  onPageChange?: (page: number) => void
  // Titles and status only, for a sidebar
  isCompact?: boolean
  emptyState: ReactNode
}

export function BlogPostList({
  blogPosts,
  isPending,
  error,
  isNarrowed,
  pagination,
  onPageChange,
  isCompact = false,
  emptyState,
}: BlogPostListProps) {
  if (isPending || !blogPosts) {
    return error ? <QueryErrorState error={error} /> : <CardListSkeleton />
  }

  if (blogPosts.length === 0) {
    // Past the last page, such as after a delete or a stale link
    if (pagination && pagination.total > 0 && onPageChange) {
      return (
        <div className="flex flex-col items-start gap-4">
          <p className="text-muted-foreground">Nothing on this page.</p>
          <Button variant="secondary" onClick={() => onPageChange(1)}>
            Go to page 1
          </Button>
        </div>
      )
    }

    // Nothing matched, or nothing exists
    return isNarrowed ? (
      <p className="break-words text-muted-foreground">No posts match your search or filter.</p>
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
