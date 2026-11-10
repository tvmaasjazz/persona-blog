import type { Ref } from 'react'

import { useFormContext } from '@/components/form/form-context'
import { Button } from '@/components/ui/button'

type SubmitButtonProps = {
  label: string
  pendingLabel?: string
  pendingHint?: string
  // For returning focus to the button, such as after a dialog closes
  ref?: Ref<HTMLButtonElement>
}

// pendingLabel and pendingHint are for a submit that runs long enough to need saying so.
export function SubmitButton({ label, pendingLabel, pendingHint, ref }: SubmitButtonProps) {
  const form = useFormContext()

  return (
    <form.Subscribe selector={(formState) => formState.isSubmitting}>
      {(isSubmitting) => (
        <div className="flex flex-col items-start gap-2">
          <Button ref={ref} type="submit" disabled={isSubmitting}>
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
