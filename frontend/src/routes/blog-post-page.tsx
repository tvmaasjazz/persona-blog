import { useParams } from 'react-router'

import { BlogPostView } from '@/features/blog-posts/components/blog-post-view'
import { usePersonaList } from '@/features/personas/api/persona-list-query'

export function BlogPostPage() {
  const { blogPostIdentity } = useParams()
  const { data: personaList } = usePersonaList()

  if (!blogPostIdentity) {
    return null
  }

  return <BlogPostView blogPostIdentity={blogPostIdentity} personas={personaList?.personas ?? []} />
}
