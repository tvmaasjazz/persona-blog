import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import { useAppForm } from '@/components/form/use-app-form'
import { useCreateBlogPostFromRun } from '@/features/blog-posts/api/use-create-blog-post-from-run'
import { PublishingFields } from '@/features/blog-posts/components/publishing-fields'
import {
  EMPTY_PUBLISHING_VALUES,
  publishingFormSchema,
  toPublishedAt,
} from '@/features/blog-posts/publishing-form-schema'
import { ApiError } from '@/lib/api-error'

const saveRunFormSchema = z.object({ publishing: publishingFormSchema })

const saveRunFormOptions = formOptions({
  defaultValues: { publishing: EMPTY_PUBLISHING_VALUES },
  validationLogic: revalidateLogic(),
  validators: { onDynamic: saveRunFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})

type SaveRunAsPostFormProps = {
  runIdentity: string
  isPersonaPublic: boolean
}

export function SaveRunAsPostForm({ runIdentity, isPersonaPublic }: SaveRunAsPostFormProps) {
  const navigate = useNavigate()
  const createBlogPostFromRun = useCreateBlogPostFromRun()

  const form = useAppForm({
    ...saveRunFormOptions,
    onSubmit: async ({ value }) => {
      const { publishing } = saveRunFormSchema.parse(value)
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
