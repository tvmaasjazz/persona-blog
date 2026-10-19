import type { ReactNode } from 'react'
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
  // Called after saving, before navigating
  onSaved?: () => void
  // Shown beside Save
  secondaryAction?: ReactNode
}

export function SaveRunAsPostForm({
  runIdentity,
  isPersonaPublic,
  onSaved,
  secondaryAction,
}: SaveRunAsPostFormProps) {
  // Form that saves the run
  const navigate = useNavigate()
  const createBlogPostFromRun = useCreateBlogPostFromRun()

  const form = useAppForm({
    ...saveRunAsPostFormOptions,
    onSubmit: async ({ value }) => {
      // Save the post, then open it
      const { publishing } = saveRunAsPostFormSchema.parse(value)
      try {
        const blogPostIdentity = await createBlogPostFromRun.mutateAsync({
          generate_text_run_identity: runIdentity,
          is_public: publishing.isPublic,
          published_at: toPublishedAt(publishing),
        })
        toast.success('Post saved')
        onSaved?.()
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

  // Publishing fields, then Save and any extra action
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
      <div className="flex flex-wrap items-start gap-3">
        <form.AppForm>
          <form.SubmitButton label="Save post" />
        </form.AppForm>
        {secondaryAction}
      </div>
    </form>
  )
}
