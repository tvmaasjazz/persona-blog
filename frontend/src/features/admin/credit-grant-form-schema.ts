import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import { creditAmountUsdSchema } from '@/features/admin/credit-amount-schema'

// Limits mirror AdminCreditGrantDto in the backend.
export const creditGrantFormSchema = z.object({
  amount_usd: creditAmountUsdSchema,
  note: z
    .string()
    .trim()
    .min(1, 'Note is required')
    .max(500, 'Note must be 500 characters or fewer'),
})

type CreditGrantFormValues = z.input<typeof creditGrantFormSchema>

const EMPTY_CREDIT_GRANT_FORM_VALUES: CreditGrantFormValues = { amount_usd: '', note: '' }

export const creditGrantFormOptions = formOptions({
  defaultValues: EMPTY_CREDIT_GRANT_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: creditGrantFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
