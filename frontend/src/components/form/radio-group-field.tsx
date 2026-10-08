import { FormField } from '@/components/form/form-field'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

type RadioGroupFieldProps = {
  label: string
  description?: string
  options: { value: string; label: string; description?: string }[]
}

export function RadioGroupField({ label, description, options }: RadioGroupFieldProps) {
  return (
    <FormField<string> label={label} description={description}>
      {({ id, value, onChange, onBlur, ...controlProps }) => (
        <RadioGroup
          {...controlProps}
          id={id}
          value={value}
          onValueChange={onChange}
          onBlur={onBlur}
        >
          {options.map((option) => (
            <div key={option.value} className="flex items-start gap-3">
              <RadioGroupItem value={option.value} id={`${id}-${option.value}`} className="mt-1" />
              <div className="flex flex-col gap-1">
                <Label htmlFor={`${id}-${option.value}`}>{option.label}</Label>
                {option.description && (
                  <p className="text-sm text-muted-foreground">{option.description}</p>
                )}
              </div>
            </div>
          ))}
        </RadioGroup>
      )}
    </FormField>
  )
}
