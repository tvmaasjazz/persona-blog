import { useAppForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
import {
  reviewFeedbackFormOptions,
  reviewFeedbackFormSchema,
} from '@/features/generate-text/review-feedback-form-schema'

type RequestChangesFormProps = {
  isDisabled: boolean
  onSend: (feedbackText: string) => Promise<void>
  onCancel: () => void
}

// The feedback half of a review. RunReview owns the resume call, so Approve and Send
// share one working state.
export function RequestChangesForm({ isDisabled, onSend, onCancel }: RequestChangesFormProps) {
  const form = useAppForm({
    ...reviewFeedbackFormOptions,
    onSubmit: async ({ value }) => {
      const { feedback_text } = reviewFeedbackFormSchema.parse(value)
      await onSend(feedback_text)
    },
  })

  return (
    <form
      noValidate
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        void form.handleSubmit()
      }}
    >
      <form.AppField name="feedback_text">
        {(field) => <field.TextareaField label="What should change?" />}
      </form.AppField>
      <div className="flex gap-3">
        <form.AppForm>
          <form.SubmitButton label="Send" pendingLabel="Sending…" />
        </form.AppForm>
        <Button type="button" variant="ghost" disabled={isDisabled} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
