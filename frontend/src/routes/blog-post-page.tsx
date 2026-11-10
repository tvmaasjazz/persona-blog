import { useParams } from 'react-router'

import { QueryErrorState } from '@/components/query-error-state'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import { usePublicBlogPost } from '@/features/blog-posts/api/public-blog-post-query'
import { BlogPostView } from '@/features/blog-posts/components/blog-post-view'

export function BlogPostPage() {
  const { blogPostIdentity = '' } = useParams()
  const { data: blogPost, isPending, error } = usePublicBlogPost(blogPostIdentity)
  const { data: user } = useCurrentUser()

  if (isPending) {
    return (
      <div className="flex flex-col gap-4" aria-hidden>
        <div className="h-8 w-3/4 rounded-2xl bg-accent" />
        <div className="h-12 w-1/2 rounded-2xl bg-accent" />
        <div className="h-64 rounded-2xl bg-accent" />
      </div>
    )
  }

  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Post not found."
        backTo={{ to: '/', label: 'Go home' }}
      />
    )
  }

  // Edit and Delete are for the owner who may write posts
  const canEdit = blogPost.is_owner && hasPermission(user, 'BLOG_POST_WRITE')

  return <BlogPostView blogPost={blogPost} canEdit={canEdit} />
}
