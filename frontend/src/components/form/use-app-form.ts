import { createFormHook } from '@tanstack/react-form'

import { DateTimeField } from '@/components/form/date-time-field'
import { fieldContext, formContext } from '@/components/form/form-context'
import { RadioGroupField } from '@/components/form/radio-group-field'
import { SelectField } from '@/components/form/select-field'
import { SubmitButton } from '@/components/form/submit-button'
import { SwitchField } from '@/components/form/switch-field'
import { TextField } from '@/components/form/text-field'
import { TextareaField } from '@/components/form/textarea-field'

// The app's form hook. Every form uses useAppForm, and a form split across
// components uses withForm, and fields reused across forms use withFieldGroup. A new kind of field is a component in this folder,
// registered here.
export const { useAppForm, withForm, withFieldGroup } = createFormHook({
  fieldContext,
  formContext,
  fieldComponents: {
    TextField,
    TextareaField,
    SwitchField,
    SelectField,
    RadioGroupField,
    DateTimeField,
  },
  formComponents: { SubmitButton },
})
