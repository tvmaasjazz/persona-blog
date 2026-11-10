import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useGrantUserCredits } from '@/features/admin/api/use-grant-user-credits'
import {
  creditGrantFormOptions,
  creditGrantFormSchema,
} from '@/features/admin/credit-grant-form-schema'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type GrantCreditsFormProps = {
  userIdentity: string
  isOwnAccount: boolean
}

export function GrantCreditsForm({ userIdentity, isOwnAccount }: GrantCreditsFormProps) {
  const grantUserCredits = useGrantUserCredits(userIdentity, isOwnAccount)

  const form = useAppForm({
    ...creditGrantFormOptions,
    onSubmit: async ({ value, formApi }) => {
      // Grant, then clear the form
      try {
        await grantUserCredits.mutateAsync(creditGrantFormSchema.parse(value))
        toast.success('Credits granted')
        formApi.reset()
      } catch (error) {
        if (!isSessionEndedError(error)) {
          toast.error(apiErrorMessage(error))
        }
      }
    },
  })

  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <h2 className="text-xl font-extrabold">Grant credits</h2>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.AppField name="amount_usd">
          {(field) => (
            <field.TextField label="Amount (USD)" description="Up to $100, in cents." type="text" />
          )}
        </form.AppField>
        <form.AppField name="note">
          {(field) => (
            <field.TextareaField label="Note" description="Why the credits are granted." rows={3} />
          )}
        </form.AppField>
        <form.AppForm>
          <form.SubmitButton label="Grant credits" pendingLabel="Granting…" />
        </form.AppForm>
      </form>
      <p className="text-sm text-muted-foreground">
        A reader becomes a creator and is signed out everywhere.
      </p>
    </section>
  )
}
