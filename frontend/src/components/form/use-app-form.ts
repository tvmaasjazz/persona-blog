import { createFormHook } from '@tanstack/react-form'

import { fieldContext, formContext } from '@/components/form/form-context'
import { SubmitButton } from '@/components/form/submit-button'
import { SwitchField } from '@/components/form/switch-field'
import { TextField } from '@/components/form/text-field'
import { TextareaField } from '@/components/form/textarea-field'

// The app's form hook. Every form uses useAppForm, and a form split across
// components uses withForm. A new kind of field is a component in this folder,
// registered here.
export const { useAppForm, withForm } = createFormHook({
  fieldContext,
  formContext,
  fieldComponents: { TextField, TextareaField, SwitchField },
  formComponents: { SubmitButton },
})
