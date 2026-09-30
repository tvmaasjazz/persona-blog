import type { AnyFormApi } from '@tanstack/react-form'

// An error the API returned for one field, such as a 409 name clash. It sits in the
// field's onServer slot, which no validator writes, and FormField clears it when the
// user edits that field.
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

// For a form's onSubmitInvalid, so a failed submit lands on the first error even
// when it's scrolled out of view. Waits a frame for FormField to mark it invalid.
export function focusFirstInvalidField() {
  requestAnimationFrame(() => {
    document.querySelector<HTMLElement>('form [aria-invalid="true"]')?.focus()
  })
}
