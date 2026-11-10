import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { QueryErrorState } from '@/components/query-error-state'
import { useBlogPost } from '@/features/blog-posts/api/blog-post-query'
import { useUpdateBlogPost } from '@/features/blog-posts/api/use-update-blog-post'
import {
  blogPostFormOptions,
  blogPostFormSchema,
} from '@/features/blog-posts/blog-post-form-schema'
import { BlogPostForm } from '@/features/blog-posts/components/blog-post-form'
import {
  publishingValuesFromPost,
  toPublishedAt,
} from '@/features/blog-posts/publishing-form-schema'
import { apiErrorMessage } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type BlogPostResponseDto = components['schemas']['BlogPostResponseDto']

type EditBlogPostFormProps = {
  blogPostIdentity: string
}

export function EditBlogPostForm({ blogPostIdentity }: EditBlogPostFormProps) {
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

  // The post's persona decides whether it can be public
  return <LoadedEditBlogPostForm blogPost={blogPost} isPersonaPublic={blogPost.is_persona_public} />
}

type LoadedEditBlogPostFormProps = {
  blogPost: BlogPostResponseDto
  isPersonaPublic: boolean
}

// Split out so the form starts from the loaded post.
function LoadedEditBlogPostForm({ blogPost, isPersonaPublic }: LoadedEditBlogPostFormProps) {
  // Form starting from the post
  const navigate = useNavigate()
  const updateBlogPost = useUpdateBlogPost()

  const form = useAppForm({
    ...blogPostFormOptions,
    defaultValues: {
      title: blogPost.title,
      subtitle: blogPost.subtitle ?? '',
      publishing: publishingValuesFromPost(blogPost),
    },
    onSubmit: async ({ value }) => {
      // Save, then go to the post
      const values = blogPostFormSchema.parse(value)
      try {
        await updateBlogPost.mutateAsync({
          blogPostIdentity: blogPost.identity,
          blogPost: {
            title: values.title,
            subtitle: values.subtitle,
            body: blogPost.body,
            is_public: values.publishing.isPublic,
            published_at: toPublishedAt(values.publishing),
          },
        })
        toast.success('Post saved')
        navigate(`/posts/${blogPost.identity}`)
      } catch (error) {
        toast.error(apiErrorMessage(error))
      }
    },
  })

  return (
    <BlogPostForm
      form={form}
      submitLabel="Save changes"
      isPersonaPublic={isPersonaPublic}
      onCancel={() => navigate(`/posts/${blogPost.identity}`)}
    />
  )
}
