import { Link } from 'react-router'

import { PersonaAvatar } from '@/components/persona-avatar'
import { PostStatusBadges } from '@/features/blog-posts/components/post-status-badges'
import type { components } from '@/lib/api-schema.gen'

type BlogPostResponseDto = components['schemas']['BlogPostResponseDto']
type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type BlogPostCardProps = {
  blogPost: BlogPostResponseDto
  persona: PersonaResponseDto | undefined
}

export function BlogPostCard({ blogPost, persona }: BlogPostCardProps) {
  const personaName = persona?.name ?? 'Unknown persona'

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
        <PersonaAvatar name={personaName} avatarUrl={persona?.avatar_url ?? null} />
        <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">{personaName}</span>
        <PostStatusBadges publishedAt={blogPost.published_at} isPublic={blogPost.is_public} />
      </div>
    </Link>
  )
}
