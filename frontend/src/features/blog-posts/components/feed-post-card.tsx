import { Link } from 'react-router'

import { PersonaAvatar } from '@/components/persona-avatar'
import type { components } from '@/lib/api-schema.gen'
import { formatDate } from '@/lib/format-date'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']

type FeedPostCardProps = {
  blogPost: BlogPostSummaryResponseDto
}

export function FeedPostCard({ blogPost }: FeedPostCardProps) {
  return (
    <article className="relative flex flex-col gap-3 rounded-2xl border bg-card p-4 hover:bg-accent">
      <div className="flex min-w-0 flex-col gap-1">
        {/* The title link's ::after covers the card; the persona link sits above it */}
        <h2 className="font-bold break-words">
          <Link to={`/posts/${blogPost.identity}`} className="after:absolute after:inset-0">
            {blogPost.title}
          </Link>
        </h2>
        {blogPost.subtitle && (
          <p className="line-clamp-2 text-sm text-muted-foreground">{blogPost.subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link
          to={`/personas/${blogPost.persona_identity}`}
          className="relative z-10 flex min-w-0 items-center gap-2 hover:underline"
        >
          <PersonaAvatar name={blogPost.persona_name} avatarUrl={blogPost.persona_avatar_url} />
          <span className="min-w-0 truncate">{blogPost.persona_name}</span>
        </Link>
        {blogPost.published_at && (
          <>
            <span aria-hidden>·</span>
            <time dateTime={blogPost.published_at}>{formatDate(blogPost.published_at)}</time>
          </>
        )}
      </div>
    </article>
  )
}
