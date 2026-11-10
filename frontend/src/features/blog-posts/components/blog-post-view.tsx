import { Pencil } from 'lucide-react'
import { Link } from 'react-router'

import { MarkdownContent } from '@/components/markdown-content'
import { PersonaAvatar } from '@/components/persona-avatar'
import { Button } from '@/components/ui/button'
import { DeleteBlogPostButton } from '@/features/blog-posts/components/delete-blog-post-button'
import { PostStatusBadges } from '@/features/blog-posts/components/post-status-badges'
import type { components } from '@/lib/api-schema.gen'
import { formatDate } from '@/lib/format-date'

type BlogPostViewProps = {
  blogPost: components['schemas']['PublicBlogPostResponseDto']
  canEdit: boolean
}

export function BlogPostView({ blogPost, canEdit }: BlogPostViewProps) {
  // Title, subtitle, author and date, then the body
  return (
    <article className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <h1 className="text-xl font-extrabold break-words">{blogPost.title}</h1>
        {blogPost.subtitle && (
          <p className="break-words text-muted-foreground italic">{blogPost.subtitle}</p>
        )}
        <div className="flex items-center gap-3">
          <PersonaAvatar name={blogPost.persona_name} avatarUrl={blogPost.persona_avatar_url} />
          <div className="flex min-w-0 flex-col">
            <Link
              to={`/personas/${blogPost.persona_identity}`}
              className="font-semibold break-words text-primary-text"
            >
              {blogPost.persona_name}
            </Link>
            {blogPost.published_at && (
              <time dateTime={blogPost.published_at} className="text-sm text-muted-foreground">
                {formatDate(blogPost.published_at)}
              </time>
            )}
          </div>
        </div>
        {/* The owner's badges already show the date and visibility */}
        {blogPost.is_owner && (
          <PostStatusBadges
            publishedAt={blogPost.published_at}
            isPublic={blogPost.is_public}
            isPersonaPublic={blogPost.is_persona_public}
          />
        )}
        {canEdit && (
          <div className="flex items-center gap-2">
            <Button asChild variant="secondary">
              <Link to={`/posts/${blogPost.identity}/edit`}>
                <Pencil aria-hidden />
                Edit
              </Link>
            </Button>
            <DeleteBlogPostButton
              blogPostIdentity={blogPost.identity}
              blogPostTitle={blogPost.title}
            />
          </div>
        )}
      </header>
      <div className="font-serif">
        <MarkdownContent markdown={blogPost.body} />
      </div>
    </article>
  )
}
