import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import type { components } from '@/lib/api-schema.gen'

type GenerateBlogPostDto = components['schemas']['GenerateBlogPostDto']
type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

// A blank optional field is sent as null.
function optionalText() {
  return z
    .string()
    .trim()
    .transform((value) => value || null)
}

// Validates the form's values; parsing them gives the GenerateBlogPostDto body to send.
export const generateBlogPostFormSchema = z
  .object({
    persona_identity: z.string().min(1, 'Pick a persona'),
    prompt_text: z.string().trim().min(1, 'Prompt is required'),
    tone: optionalText(),
    target_audience: optionalText(),
    additional_context: optionalText(),
    isOutlineEnabled: z.boolean(),
    isOutlineAutoApproved: z.boolean(),
    isDraftAutoApproved: z.boolean(),
    isHumanizeEnabled: z.boolean(),
    isHumanizeAutoApproved: z.boolean(),
  })
  .transform((values): GenerateBlogPostDto => ({
    persona_identity: values.persona_identity,
    prompt_text: values.prompt_text,
    tone: values.tone,
    target_audience: values.target_audience,
    additional_context: values.additional_context,
    options: {
      outline: {
        is_enabled: values.isOutlineEnabled,
        is_auto_approved: values.isOutlineAutoApproved,
      },
      draft: { is_enabled: true, is_auto_approved: values.isDraftAutoApproved },
      humanize: {
        is_enabled: values.isHumanizeEnabled,
        is_auto_approved: values.isHumanizeAutoApproved,
      },
    },
  }))

export type GenerateBlogPostFormValues = z.input<typeof generateBlogPostFormSchema>

export const EMPTY_GENERATE_BLOG_POST_FORM_VALUES: GenerateBlogPostFormValues = {
  persona_identity: '',
  prompt_text: '',
  tone: '',
  target_audience: '',
  additional_context: '',
  isOutlineEnabled: true,
  isOutlineAutoApproved: false,
  isDraftAutoApproved: false,
  isHumanizeEnabled: true,
  isHumanizeAutoApproved: false,
}

// Checks nothing until the first submit, then rechecks as the user types.
export const generateBlogPostFormOptions = formOptions({
  defaultValues: EMPTY_GENERATE_BLOG_POST_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: generateBlogPostFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})

export function toFormValuesFromRun(
  run: GenerateTextRunResponseDto,
  personaIdentity: string,
): GenerateBlogPostFormValues {
  return {
    persona_identity: personaIdentity,
    prompt_text: run.prompt_text,
    tone: run.tone ?? '',
    target_audience: run.target_audience ?? '',
    additional_context: run.additional_context ?? '',
    isOutlineEnabled: run.options.outline?.is_enabled ?? false,
    isOutlineAutoApproved: run.options.outline?.is_auto_approved ?? false,
    isDraftAutoApproved: run.options.draft.is_auto_approved,
    isHumanizeEnabled: run.options.humanize?.is_enabled ?? false,
    isHumanizeAutoApproved: run.options.humanize?.is_auto_approved ?? false,
  }
}
