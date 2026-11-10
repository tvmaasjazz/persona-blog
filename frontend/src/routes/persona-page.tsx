import { useParams } from 'react-router'

import { useUserBlogPostPage } from '@/features/blog-posts/api/user-blog-post-page-query'
import { BlogPostList } from '@/features/blog-posts/components/blog-post-list'
import { PersonaProfile } from '@/features/personas/components/persona-profile'

export function PersonaPage() {
  const { personaIdentity } = useParams()
  const {
    data: blogPostPage,
    isPending,
    error,
  } = useUserBlogPostPage({
    page: 1,
    page_size: 20,
    persona_identity: personaIdentity,
    sort_by: 'CREATED_AT',
    sort_direction: 'DESC',
  })

  if (!personaIdentity) {
    return null
  }

  return (
    <PersonaProfile
      personaIdentity={personaIdentity}
      posts={
        <BlogPostList
          blogPosts={blogPostPage?.blog_posts}
          isPending={isPending}
          error={error}
          isNarrowed={false}
          isCompact
          emptyState={<p className="text-muted-foreground">No posts from this persona yet.</p>}
        />
      }
    />
  )
}
