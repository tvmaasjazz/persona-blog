import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useGrantUserCredits } from '@/features/admin/api/use-grant-user-credits'
import { SectionCard } from '@/features/admin/components/section-card'
import { MAX_CREDIT_GRANT_USD } from '@/features/admin/credit-amount-schema'
import {
  creditGrantFormOptions,
  creditGrantFormSchema,
} from '@/features/admin/credit-grant-form-schema'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type CreditGrantFormProps = {
  userIdentity: string
  isReader: boolean
}

export function CreditGrantForm({ userIdentity, isReader }: CreditGrantFormProps) {
  const grantUserCredits = useGrantUserCredits(userIdentity)

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
    <SectionCard title="Grant credits">
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
            <field.TextField
              label="Amount (USD)"
              description={`More than $0 and up to $${MAX_CREDIT_GRANT_USD}, to the cent.`}
              type="text"
            />
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
      {isReader && (
        <p className="text-sm text-muted-foreground">
          A reader becomes a creator and is signed out everywhere.
        </p>
      )}
    </SectionCard>
  )
}
