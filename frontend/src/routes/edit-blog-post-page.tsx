import { useParams } from 'react-router'

import { EditBlogPostForm } from '@/features/blog-posts/components/edit-blog-post-form'
import { usePersonaList } from '@/features/personas/api/persona-list-query'

export function EditBlogPostPage() {
  const { blogPostIdentity } = useParams()
  const { data: personaList, isPending } = usePersonaList()

  if (!blogPostIdentity) {
    return null
  }

  return (
    <>
      <h1 className="mb-6 text-xl font-extrabold">Edit post</h1>
      {isPending ? (
        <div className="h-40 rounded-2xl bg-accent" />
      ) : (
        <EditBlogPostForm
          blogPostIdentity={blogPostIdentity}
          personas={personaList?.personas ?? []}
        />
      )}
    </>
  )
}
