import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import {
  EMPTY_PUBLISHING_VALUES,
  publishingFormSchema,
} from '@/features/blog-posts/publishing-form-schema'

// Only publishing is asked; the server takes the rest from the run.
export const saveRunAsPostFormSchema = z.object({
  publishing: publishingFormSchema,
})

export type SaveRunAsPostFormValues = z.input<typeof saveRunAsPostFormSchema>

const EMPTY_SAVE_RUN_AS_POST_FORM_VALUES: SaveRunAsPostFormValues = {
  publishing: EMPTY_PUBLISHING_VALUES,
}

export const saveRunAsPostFormOptions = formOptions({
  defaultValues: EMPTY_SAVE_RUN_AS_POST_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: saveRunAsPostFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
