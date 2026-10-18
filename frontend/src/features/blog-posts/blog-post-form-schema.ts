import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import {
  EMPTY_PUBLISHING_VALUES,
  publishingFormSchema,
} from '@/features/blog-posts/publishing-form-schema'

// BlogPostDto has no length limits; a blank subtitle is sent as null.
export const blogPostFormSchema = z.object({
  title: z.string().trim().min(1, 'Title is required'),
  subtitle: z
    .string()
    .trim()
    .transform((value) => value || null),
  publishing: publishingFormSchema,
})

export type BlogPostFormValues = z.input<typeof blogPostFormSchema>

const EMPTY_BLOG_POST_FORM_VALUES: BlogPostFormValues = {
  title: '',
  subtitle: '',
  publishing: EMPTY_PUBLISHING_VALUES,
}

export const blogPostFormOptions = formOptions({
  defaultValues: EMPTY_BLOG_POST_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: blogPostFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
