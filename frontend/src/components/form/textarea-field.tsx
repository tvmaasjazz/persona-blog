import { FormField } from '@/components/form/form-field'
import { Textarea } from '@/components/ui/textarea'

type TextareaFieldProps = {
  label: string
  description?: string
  rows?: number
}

export function TextareaField({ label, description, rows = 4 }: TextareaFieldProps) {
  return (
    <FormField<string> label={label} description={description}>
      {({ onChange, ...controlProps }) => (
        <Textarea
          {...controlProps}
          rows={rows}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FormField>
  )
}
