import { FormField } from '@/components/form/form-field'
import { Input } from '@/components/ui/input'

type DateTimeFieldProps = {
  label: string
  description?: string
}

// The value is the input's own local format, YYYY-MM-DDTHH:mm.
export function DateTimeField({ label, description }: DateTimeFieldProps) {
  return (
    <FormField<string> label={label} description={description}>
      {({ onChange, ...controlProps }) => (
        <Input
          {...controlProps}
          type="datetime-local"
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FormField>
  )
}
