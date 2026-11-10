import { useParams } from 'react-router'

import { BlogPostView } from '@/features/blog-posts/components/blog-post-view'

export function BlogPostPage() {
  const { blogPostIdentity } = useParams()

  if (!blogPostIdentity) {
    return null
  }

  return <BlogPostView blogPostIdentity={blogPostIdentity} />
}
