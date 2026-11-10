import { useParams } from 'react-router'

import { EditBlogPostForm } from '@/features/blog-posts/components/edit-blog-post-form'

export function EditBlogPostPage() {
  const { blogPostIdentity } = useParams()

  if (!blogPostIdentity) {
    return null
  }

  return (
    <>
      <h1 className="mb-6 text-xl font-extrabold">Edit post</h1>
      <EditBlogPostForm blogPostIdentity={blogPostIdentity} />
    </>
  )
}
