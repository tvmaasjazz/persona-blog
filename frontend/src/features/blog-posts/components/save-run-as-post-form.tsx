import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useCreateBlogPostFromRun } from '@/features/blog-posts/api/use-create-blog-post-from-run'
import { PublishingFields } from '@/features/blog-posts/components/publishing-fields'
import { toPublishedAt } from '@/features/blog-posts/publishing-form-schema'
import {
  saveRunAsPostFormOptions,
  saveRunAsPostFormSchema,
} from '@/features/blog-posts/save-run-as-post-form-schema'
import { ApiError } from '@/lib/api-error'

type SaveRunAsPostFormProps = {
  runIdentity: string
  isPersonaPublic: boolean
}

export function SaveRunAsPostForm({ runIdentity, isPersonaPublic }: SaveRunAsPostFormProps) {
  const navigate = useNavigate()
  const createBlogPostFromRun = useCreateBlogPostFromRun()

  const form = useAppForm({
    ...saveRunAsPostFormOptions,
    onSubmit: async ({ value }) => {
      const { publishing } = saveRunAsPostFormSchema.parse(value)
      try {
        const blogPostIdentity = await createBlogPostFromRun.mutateAsync({
          generate_text_run_identity: runIdentity,
          is_public: publishing.isPublic,
          published_at: toPublishedAt(publishing),
        })
        toast.success('Post saved')
        navigate(`/posts/${blogPostIdentity}`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          toast.error('This post is already saved.')
        } else {
          toast.error("Couldn't save the post. Try again.")
        }
      }
    },
  })

  return (
    <form
      noValidate
      className="flex flex-col gap-6"
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
    >
      <PublishingFields form={form} fields="publishing" isPersonaPublic={isPersonaPublic} />
      <div className="flex">
        <form.AppForm>
          <form.SubmitButton label="Save post" />
        </form.AppForm>
      </div>
    </form>
  )
}
