import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import {
  EMPTY_PUBLISHING_VALUES,
  publishingFormSchema,
} from '@/features/blog-posts/publishing-form-schema'

// Saving a finished run only asks how to publish it: the server takes the title,
// subtitle and body from the run.
export const saveRunAsPostFormSchema = z.object({
  publishing: publishingFormSchema,
})

export type SaveRunAsPostFormValues = z.input<typeof saveRunAsPostFormSchema>

const EMPTY_SAVE_RUN_AS_POST_FORM_VALUES: SaveRunAsPostFormValues = {
  publishing: EMPTY_PUBLISHING_VALUES,
}

// Checks nothing until the first submit, then rechecks as the user types.
export const saveRunAsPostFormOptions = formOptions({
  defaultValues: EMPTY_SAVE_RUN_AS_POST_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: saveRunAsPostFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
