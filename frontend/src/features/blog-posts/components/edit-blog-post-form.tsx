import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
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
import { ApiError, apiErrorMessage } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type BlogPostResponseDto = components['schemas']['BlogPostResponseDto']
type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type EditBlogPostFormProps = {
  blogPostIdentity: string
  personas: PersonaResponseDto[]
}

export function EditBlogPostForm({ blogPostIdentity, personas }: EditBlogPostFormProps) {
  // Load the post
  const { data: blogPost, isPending, error } = useBlogPost(blogPostIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  // Not found or failed
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

  // The post's persona decides whether it can be public
  const persona = personas.find((candidate) => candidate.identity === blogPost.persona_identity)

  return (
    <LoadedEditBlogPostForm blogPost={blogPost} isPersonaPublic={persona?.is_public ?? false} />
  )
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
