import { FormField } from '@/components/form/form-field'
import { Switch } from '@/components/ui/switch'

type SwitchFieldProps = {
  label: string
  description?: string
  isDisabled?: boolean
}

export function SwitchField({ label, description, isDisabled = false }: SwitchFieldProps) {
  return (
    <FormField<boolean> label={label} description={description} isInline>
      {({ value, onChange, ...controlProps }) => (
        <Switch
          {...controlProps}
          checked={value}
          disabled={isDisabled}
          onCheckedChange={onChange}
        />
      )}
    </FormField>
  )
}
