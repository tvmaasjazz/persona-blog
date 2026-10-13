import { useStore } from '@tanstack/react-form'
import { LoaderCircle } from 'lucide-react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useGenerateBlogPost } from '@/features/generate-text/api/use-generate-blog-post'
import {
  GenerateBlogPostForm,
  type PersonaChoice,
} from '@/features/generate-text/components/generate-blog-post-form'
import { RunInputsSummary } from '@/features/generate-text/components/run-inputs-summary'
import {
  generateBlogPostFormOptions,
  generateBlogPostFormSchema,
  type GenerateBlogPostFormValues,
} from '@/features/generate-text/generate-blog-post-form-schema'
import { describeRunReady, describeSteps } from '@/features/generate-text/run-steps'

type WriteBlogPostFormProps = {
  personas: PersonaChoice[]
  initialValues: GenerateBlogPostFormValues
}

export function WriteBlogPostForm({ personas, initialValues }: WriteBlogPostFormProps) {
  const navigate = useNavigate()
  const generateBlogPost = useGenerateBlogPost()

  const form = useAppForm({
    ...generateBlogPostFormOptions,
    defaultValues: initialValues,
    onSubmit: async ({ value }) => {
      // The form folds into the status card, which sits where the top of the form was.
      window.scrollTo({ top: 0 })
      try {
        const run = await generateBlogPost.mutateAsync(generateBlogPostFormSchema.parse(value))
        const runReadyMessage = describeRunReady(run)
        if (runReadyMessage) {
          toast.success(runReadyMessage)
        }
        navigate(`/write/runs/${run.run_identity}`)
      } catch {
        toast.error("Couldn't write the post. Try again.")
      }
    },
  })

  const isSubmitting = useStore(form.store, (formState) => formState.isSubmitting)
  const values = useStore(form.store, (formState) => formState.values)
  const persona = personas.find((choice) => choice.identity === values.persona_identity)

  return (
    <>
      {isSubmitting && (
        <RunInputsSummary
          title="Writing your post…"
          status={
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <LoaderCircle aria-hidden className="size-4 animate-spin" />
              This can take a minute or more. Keep this page open.
            </p>
          }
          personaName={persona?.name ?? ''}
          promptText={values.prompt_text}
          tone={values.tone || null}
          targetAudience={values.target_audience || null}
          additionalContext={values.additional_context || null}
          stepsLabel={describeSteps({
            isOutlineEnabled: values.isOutlineEnabled,
            isHumanizeEnabled: values.isHumanizeEnabled,
          })}
        />
      )}
      {/* Hidden rather than unmounted, so a failed request leaves every field as it was. */}
      <div hidden={isSubmitting}>
        <GenerateBlogPostForm form={form} personas={personas} />
      </div>
    </>
  )
}
