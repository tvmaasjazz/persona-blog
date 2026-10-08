import { formOptions, revalidateLogic } from '@tanstack/react-form'
import { z } from 'zod'

import { focusFirstInvalidField } from '@/components/form/form-errors'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

// The limits mirror PersonaDto in backend/apps/api/domains/personas/dtos.py.
function requiredText(label: string, maxLength: number) {
  return z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .max(maxLength, `${label} must be ${maxLength} characters or fewer`)
}

// A blank optional field is sent as null.
function optionalText(label: string, maxLength: number) {
  return z
    .string()
    .trim()
    .max(maxLength, `${label} must be ${maxLength} characters or fewer`)
    .transform((value) => value || null)
}

// Validates the form's values; parsing them gives the PersonaDto body to send.
export const personaFormSchema = z.object({
  name: requiredText('Name', 80),
  bio: requiredText('Bio', 500),
  avatar_url: optionalText('Avatar URL', 2048).refine(
    (avatarUrl) => avatarUrl === null || /^https?:\/\//.test(avatarUrl),
    'Avatar URL must start with http:// or https://',
  ),
  is_public: z.boolean(),
  background: optionalText('Background', 2000),
  expertise: optionalText('Expertise', 2000),
  writing_style: optionalText('Writing style', 2000),
  sample_writing: optionalText('Sample writing', 10000),
  default_tone: optionalText('Default tone', 200),
  default_target_audience: optionalText('Default target audience', 200),
})

type PersonaFormValues = z.input<typeof personaFormSchema>

const EMPTY_PERSONA_FORM_VALUES: PersonaFormValues = {
  name: '',
  bio: '',
  avatar_url: '',
  is_public: false,
  background: '',
  expertise: '',
  writing_style: '',
  sample_writing: '',
  default_tone: '',
  default_target_audience: '',
}

// Checks nothing until the first submit, then rechecks as the user types.
export const personaFormOptions = formOptions({
  defaultValues: EMPTY_PERSONA_FORM_VALUES,
  validationLogic: revalidateLogic(),
  validators: { onDynamic: personaFormSchema },
  onSubmitInvalid: focusFirstInvalidField,
})

export function toPersonaFormValues(persona: PersonaResponseDto): PersonaFormValues {
  return {
    name: persona.name,
    bio: persona.bio,
    avatar_url: persona.avatar_url ?? '',
    is_public: persona.is_public,
    background: persona.background ?? '',
    expertise: persona.expertise ?? '',
    writing_style: persona.writing_style ?? '',
    sample_writing: persona.sample_writing ?? '',
    default_tone: persona.default_tone ?? '',
    default_target_audience: persona.default_target_audience ?? '',
  }
}
