import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useGenerateBlogPost } from '@/features/generate-text/api/use-generate-blog-post'
import {
  GenerateBlogPostForm,
  type PersonaChoice,
} from '@/features/generate-text/components/generate-blog-post-form'
import {
  generateBlogPostFormOptions,
  generateBlogPostFormSchema,
  type GenerateBlogPostFormValues,
} from '@/features/generate-text/generate-blog-post-form-schema'

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
      try {
        const run = await generateBlogPost.mutateAsync(generateBlogPostFormSchema.parse(value))
        navigate(`/write/runs/${run.run_identity}`)
      } catch {
        toast.error("Couldn't write the post. Try again.")
      }
    },
  })

  return <GenerateBlogPostForm form={form} personas={personas} />
}
