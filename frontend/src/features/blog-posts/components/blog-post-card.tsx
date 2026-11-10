import { Link } from 'react-router'

import { PersonaAvatar } from '@/components/persona-avatar'
import { PostStatusBadges } from '@/features/blog-posts/components/post-status-badges'
import type { components } from '@/lib/api-schema.gen'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']

type BlogPostCardProps = {
  blogPost: BlogPostSummaryResponseDto
  isCompact?: boolean
}

export function BlogPostCard({ blogPost, isCompact = false }: BlogPostCardProps) {
  // Compact: title and status
  if (isCompact) {
    return (
      <Link
        to={`/posts/${blogPost.identity}`}
        className="flex flex-col gap-2 rounded-2xl border bg-card p-4 hover:bg-accent"
      >
        <span className="font-bold break-words">{blogPost.title}</span>
        <PostStatusBadges
          publishedAt={blogPost.published_at}
          isPublic={blogPost.is_public}
          isPersonaPublic={blogPost.is_persona_public}
        />
      </Link>
    )
  }

  // Full: title, subtitle, author, status
  return (
    <Link
      to={`/posts/${blogPost.identity}`}
      className="flex flex-col gap-3 rounded-2xl border bg-card p-4 hover:bg-accent"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <span className="font-bold break-words">{blogPost.title}</span>
        {blogPost.subtitle && (
          <p className="line-clamp-2 text-sm text-muted-foreground">{blogPost.subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <PersonaAvatar name={blogPost.persona_name} avatarUrl={blogPost.persona_avatar_url} />
        <span className="min-w-0 truncate text-sm text-muted-foreground">
          {blogPost.persona_name}
        </span>
      </div>
      <div>
        <PostStatusBadges
          publishedAt={blogPost.published_at}
          isPublic={blogPost.is_public}
          isPersonaPublic={blogPost.is_persona_public}
        />
      </div>
    </Link>
  )
}
