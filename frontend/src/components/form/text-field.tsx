import type { ComponentProps } from 'react'

import { FormField } from '@/components/form/form-field'
import { Input } from '@/components/ui/input'

type TextFieldProps = {
  label: string
  description?: string
  type?: ComponentProps<typeof Input>['type']
}

export function TextField({ label, description, type = 'text' }: TextFieldProps) {
  return (
    <FormField<string> label={label} description={description}>
      {({ onChange, ...controlProps }) => (
        <Input {...controlProps} type={type} onChange={(event) => onChange(event.target.value)} />
      )}
    </FormField>
  )
}
