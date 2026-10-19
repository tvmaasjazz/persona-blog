import { useId } from 'react'
import type { ReactNode } from 'react'

import { useFieldContext } from '@/components/form/form-context'
import { fieldErrorMessage } from '@/components/form/form-errors'
import { Label } from '@/components/ui/label'

export type FormFieldControlProps<TValue> = {
  id: string
  value: TValue
  onChange: (value: TValue) => void
  onBlur: () => void
  'aria-describedby': string
  'aria-invalid': true | undefined
}

type FormFieldProps<TValue> = {
  label: string
  description?: string
  // Puts the label beside the control, as for a switch
  isInline?: boolean
  children: (controlProps: FormFieldControlProps<TValue>) => ReactNode
}

// Label, control, description and first error for the field in context.
export function FormField<TValue>({
  label,
  description,
  isInline = false,
  children,
}: FormFieldProps<TValue>) {
  // Ids and the first error
  const field = useFieldContext<TValue>()
  const id = useId()
  const descriptionId = `${id}-description`
  const errorId = `${id}-error`
  const errorMessage = fieldErrorMessage(field.state.meta.errors[0])

  // The control, wired to the field; editing clears a server error
  const control = children({
    id,
    value: field.state.value,
    onChange: (value) => {
      if (field.state.meta.errorMap.onServer) {
        field.setMeta((fieldMeta) => ({
          ...fieldMeta,
          errorMap: { ...fieldMeta.errorMap, onServer: undefined },
        }))
      }
      field.handleChange(value)
    },
    onBlur: field.handleBlur,
    'aria-describedby': [description && descriptionId, errorMessage && errorId]
      .filter(Boolean)
      .join(' '),
    'aria-invalid': errorMessage ? true : undefined,
  })

  // Label and control, then description and error
  return (
    <div className="flex flex-col gap-2">
      {isInline ? (
        <div className="flex items-center gap-3">
          {control}
          <Label htmlFor={id}>{label}</Label>
        </div>
      ) : (
        <>
          <Label htmlFor={id}>{label}</Label>
          {control}
        </>
      )}
      {description && (
        <p id={descriptionId} className="text-sm text-muted-foreground">
          {description}
        </p>
      )}
      {errorMessage && (
        <p id={errorId} className="text-sm text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  )
}
