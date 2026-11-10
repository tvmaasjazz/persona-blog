import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'

// The grant limit in libs.admin.constants.MAX_CREDIT_GRANT_USD.
export const MAX_CREDIT_GRANT_USD = 100

// Limits mirror AdminCreditGrantDto in the backend, with the amount held to cents.
export const creditGrantFormSchema = z.object({
  amount_usd: z
    .string()
    .trim()
    .min(1, 'Amount is required')
    .regex(/^\d+(\.\d{1,2})?$/, 'Amount must be a number with up to two decimals')
    .refine((amount) => Number(amount) > 0, 'Amount must be more than $0')
    .refine(
      (amount) => Number(amount) <= MAX_CREDIT_GRANT_USD,
      `Amount must be $${MAX_CREDIT_GRANT_USD} or less`,
    ),
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
