import { FormField } from '@/components/form/form-field'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type SelectFieldProps = {
  label: string
  description?: string
  placeholder?: string
  options: { value: string; label: string }[]
}

export function SelectField({ label, description, placeholder, options }: SelectFieldProps) {
  return (
    <FormField<string> label={label} description={description}>
      {({ value, onChange, onBlur, ...controlProps }) => (
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger {...controlProps} onBlur={onBlur} className="w-full">
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </FormField>
  )
}
