import { useFormContext } from '@/components/form/form-context'
import { Button } from '@/components/ui/button'

type SubmitButtonProps = {
  label: string
  pendingLabel?: string
  pendingHint?: string
}

// pendingLabel and pendingHint are for a submit that runs long enough to need saying so.
export function SubmitButton({ label, pendingLabel, pendingHint }: SubmitButtonProps) {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(formState) => formState.isSubmitting}>
      {(isSubmitting) => (
        <div className="flex flex-col items-start gap-2">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && pendingLabel ? pendingLabel : label}
          </Button>
          {isSubmitting && pendingHint && (
            <p className="text-sm text-muted-foreground">{pendingHint}</p>
          )}
        </div>
      )}
    </form.Subscribe>
  )
}
