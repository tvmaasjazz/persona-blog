import type { ReactNode } from 'react'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { InfiniteScrollSentinel } from '@/components/infinite-scroll-sentinel'
import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import {
  usePublicBlogPostPageInfinite,
  type PublicBlogPostPageInfiniteParams,
} from '@/features/blog-posts/api/public-blog-post-page-infinite-query'
import { FeedPostCard } from '@/features/blog-posts/components/feed-post-card'

type PublicBlogPostFeedProps = {
  params: PublicBlogPostPageInfiniteParams
  // A search is narrowing the feed
  isNarrowed: boolean
  emptyMessage: ReactNode
  noMatchMessage: ReactNode
}

export function PublicBlogPostFeed({
  params,
  isNarrowed,
  emptyMessage,
  noMatchMessage,
}: PublicBlogPostFeedProps) {
  const {
    data: blogPosts,
    error,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = usePublicBlogPostPageInfinite(params)

  // Loading, or failed before any page arrived
  if (!blogPosts) {
    return error ? <QueryErrorState error={error} /> : <CardListSkeleton />
  }

  // Nothing matched, or nothing exists
  if (blogPosts.length === 0) {
    return isNarrowed ? noMatchMessage : emptyMessage
  }

  // The posts, then a loading row, a retry, the end line, or the sentinel
  return (
    <div className="flex flex-col gap-3">
      {blogPosts.map((blogPost) => (
        <FeedPostCard key={blogPost.identity} blogPost={blogPost} />
      ))}
      {isFetchingNextPage && <p className="text-sm text-muted-foreground">Loading more posts…</p>}
      {isFetchNextPageError && (
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted-foreground">Couldn't load more posts.</p>
          <Button variant="secondary" onClick={() => fetchNextPage()}>
            Try again
          </Button>
        </div>
      )}
      {!hasNextPage && <p className="text-sm text-muted-foreground">That's every post.</p>}
      {/* Keyed by count so it fires again when it is still in view after a page loads */}
      {hasNextPage && !isFetchingNextPage && !isFetchNextPageError && (
        <InfiniteScrollSentinel key={blogPosts.length} onReached={() => fetchNextPage()} />
      )}
    </div>
  )
}
