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
import { describeSteps } from '@/features/generate-text/run-steps'

type WriteBlogPostFormProps = {
  personas: PersonaChoice[]
  initialValues: GenerateBlogPostFormValues
}

export function WriteBlogPostForm({ personas, initialValues }: WriteBlogPostFormProps) {
  // Form that starts a run, then opens it
  const navigate = useNavigate()
  const generateBlogPost = useGenerateBlogPost()

  const form = useAppForm({
    ...generateBlogPostFormOptions,
    defaultValues: initialValues,
    onSubmit: async ({ value }) => {
      // The form folds into the status card at the top
      window.scrollTo({ top: 0 })
      try {
        const run = await generateBlogPost.mutateAsync(generateBlogPostFormSchema.parse(value))
        navigate(`/write/runs/${run.run_identity}`)
      } catch {
        toast.error("Couldn't write the post. Try again.")
      }
    },
  })

  // Values for the summary card
  const isSubmitting = useStore(form.store, (formState) => formState.isSubmitting)
  const values = useStore(form.store, (formState) => formState.values)
  const persona = personas.find((choice) => choice.identity === values.persona_identity)

  // Summary while submitting, then the form
  return (
    <>
      {isSubmitting && (
        <RunInputsSummary
          title="Writing your post…"
          status={
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <LoaderCircle aria-hidden className="size-4 animate-spin" />
              Starting your post…
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
      {/* Hidden, not unmounted, so a failed request keeps the fields */}
      <div hidden={isSubmitting}>
        <GenerateBlogPostForm form={form} personas={personas} />
      </div>
    </>
  )
}
