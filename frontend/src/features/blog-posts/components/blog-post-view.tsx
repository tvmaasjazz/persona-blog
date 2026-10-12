import { Pencil } from 'lucide-react'
import { Link } from 'react-router'

import { MarkdownContent } from '@/components/markdown-content'
import { PersonaAvatar } from '@/components/persona-avatar'
import { Button } from '@/components/ui/button'
import { useBlogPost } from '@/features/blog-posts/api/blog-post-query'
import { DeleteBlogPostButton } from '@/features/blog-posts/components/delete-blog-post-button'
import { PostStatusBadges } from '@/features/blog-posts/components/post-status-badges'
import { ApiError, apiErrorMessage } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type BlogPostViewProps = {
  blogPostIdentity: string
  personas: PersonaResponseDto[]
}

export function BlogPostView({ blogPostIdentity, personas }: BlogPostViewProps) {
  const { data: blogPost, isPending, error } = useBlogPost(blogPostIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-muted-foreground">
          {isNotFound ? 'Post not found' : apiErrorMessage(error)}
        </p>
        <Button asChild variant="secondary">
          <Link to="/posts">Back to posts</Link>
        </Button>
      </div>
    )
  }

  const persona = personas.find((candidate) => candidate.identity === blogPost.persona_identity)

  return (
    <article className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <h1 className="text-xl font-extrabold break-words">{blogPost.title}</h1>
        {blogPost.subtitle && <p className="text-muted-foreground italic">{blogPost.subtitle}</p>}
        <div className="flex items-center gap-2">
          <PersonaAvatar
            name={persona?.name ?? 'Unknown persona'}
            avatarUrl={persona?.avatar_url ?? null}
          />
          {persona ? (
            <Link to={`/personas/${persona.identity}`} className="font-semibold text-primary-text">
              {persona.name}
            </Link>
          ) : (
            <span className="text-muted-foreground">Unknown persona</span>
          )}
        </div>
        <PostStatusBadges publishedAt={blogPost.published_at} isPublic={blogPost.is_public} />
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
      </header>
      <MarkdownContent markdown={blogPost.body} />
    </article>
  )
}
