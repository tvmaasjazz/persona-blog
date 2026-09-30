import { FormField } from '@/components/form/form-field'
import { Switch } from '@/components/ui/switch'

type SwitchFieldProps = {
  label: string
  description?: string
}

export function SwitchField({ label, description }: SwitchFieldProps) {
  return (
    <FormField<boolean> label={label} description={description} isInline>
      {({ value, onChange, ...controlProps }) => (
        <Switch {...controlProps} checked={value} onCheckedChange={onChange} />
      )}
    </FormField>
  )
}
