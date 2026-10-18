import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'

// No length limit on feedback_text.
export const reviewFeedbackFormSchema = z.object({
  feedback_text: z.string().trim().min(1, 'Say what should change'),
})

export type ReviewFeedbackFormValues = z.input<typeof reviewFeedbackFormSchema>

const EMPTY_REVIEW_FEEDBACK_FORM_VALUES: ReviewFeedbackFormValues = {
  feedback_text: '',
}

export const reviewFeedbackFormOptions = formOptions({
  defaultValues: EMPTY_REVIEW_FEEDBACK_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: reviewFeedbackFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
