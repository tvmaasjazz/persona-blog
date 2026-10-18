import type { AnyFormApi } from '@tanstack/react-form'

// Shows an API error on one field; FormField clears it when the field is edited.
export function setFieldServerError(form: AnyFormApi, fieldName: string, message: string) {
  form.setFieldMeta(fieldName, (fieldMeta) => ({
    ...fieldMeta,
    errorMap: { ...fieldMeta.errorMap, onServer: message },
  }))
}

// Validators return strings; a Zod schema returns issues with a message.
export function fieldErrorMessage(fieldError: unknown): string | undefined {
  if (typeof fieldError === 'string') {
    return fieldError
  }

  if (typeof fieldError === 'object' && fieldError !== null && 'message' in fieldError) {
    return String(fieldError.message)
  }

  return undefined
}

// Focuses the first invalid field after a failed submit; waits a frame for aria-invalid.
export function focusFirstInvalidField() {
  requestAnimationFrame(() => {
    document.querySelector<HTMLElement>('form [aria-invalid="true"]')?.focus()
  })
}
