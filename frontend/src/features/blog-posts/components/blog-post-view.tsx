import { Pencil } from 'lucide-react'
import { Link } from 'react-router'

import { MarkdownContent } from '@/components/markdown-content'
import { PersonaAvatar } from '@/components/persona-avatar'
import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { useBlogPost } from '@/features/blog-posts/api/blog-post-query'
import { DeleteBlogPostButton } from '@/features/blog-posts/components/delete-blog-post-button'
import { PostStatusBadges } from '@/features/blog-posts/components/post-status-badges'

type BlogPostViewProps = {
  blogPostIdentity: string
}

export function BlogPostView({ blogPostIdentity }: BlogPostViewProps) {
  // Load the post
  const { data: blogPost, isPending, error } = useBlogPost(blogPostIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Post not found."
        backTo={{ to: '/posts', label: 'Back to posts' }}
      />
    )
  }

  // Header with author and actions, then the body
  return (
    <article className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <h1 className="text-xl font-extrabold break-words">{blogPost.title}</h1>
        {blogPost.subtitle && <p className="text-muted-foreground italic">{blogPost.subtitle}</p>}
        <div className="flex items-center gap-2">
          <PersonaAvatar name={blogPost.persona_name} avatarUrl={blogPost.persona_avatar_url} />
          <Link
            to={`/personas/${blogPost.persona_identity}`}
            className="font-semibold text-primary-text"
          >
            {blogPost.persona_name}
          </Link>
        </div>
        <PostStatusBadges
          publishedAt={blogPost.published_at}
          isPublic={blogPost.is_public}
          isPersonaPublic={blogPost.is_persona_public}
        />
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
