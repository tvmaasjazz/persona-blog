import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import { creditAmountUsdSchema } from '@/features/admin/credit-grant-form-schema'

// The limits in libs.invites.constants and libs.admin.constants.
export const DEFAULT_INVITE_EXPIRES_IN_DAYS = 7
export const MAX_INVITE_EXPIRES_IN_DAYS = 30

// Limits mirror AdminInviteDto in the backend.
export const inviteFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Name is required')
    .max(200, 'Name must be 200 characters or fewer'),
  credit_amount_usd: creditAmountUsdSchema,
  note: z
    .string()
    .trim()
    .max(500, 'Note must be 500 characters or fewer')
    .transform((note) => note || null),
  expires_in_days: z
    .string()
    .trim()
    .regex(/^\d+$/, 'Days must be a whole number')
    .transform(Number)
    .refine(
      (days) => days >= 1 && days <= MAX_INVITE_EXPIRES_IN_DAYS,
      `Days must be between 1 and ${MAX_INVITE_EXPIRES_IN_DAYS}`,
    ),
})

type InviteFormValues = z.input<typeof inviteFormSchema>

const EMPTY_INVITE_FORM_VALUES: InviteFormValues = {
  name: '',
  credit_amount_usd: '',
  note: '',
  expires_in_days: String(DEFAULT_INVITE_EXPIRES_IN_DAYS),
}

export const inviteFormOptions = formOptions({
  defaultValues: EMPTY_INVITE_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: inviteFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})
