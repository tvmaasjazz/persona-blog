import { useFormContext } from '@/components/form/form-context'
import { Button } from '@/components/ui/button'

type SubmitButtonProps = {
  label: string
}

export function SubmitButton({ label }: SubmitButtonProps) {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(formState) => formState.isSubmitting}>
      {(isSubmitting) => (
        <Button type="submit" disabled={isSubmitting}>
          {label}
        </Button>
      )}
    </form.Subscribe>
  )
}
