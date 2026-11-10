import { useState } from 'react'
import { toast } from 'sonner'

import { useAppForm } from '@/components/form/use-app-form'
import { useCreateInvite } from '@/features/admin/api/use-create-invite'
import { InviteLinkDialog } from '@/features/admin/components/invite-link-dialog'
import { SectionCard } from '@/features/admin/components/section-card'
import { MAX_CREDIT_GRANT_USD } from '@/features/admin/credit-grant-form-schema'
import {
  MAX_INVITE_EXPIRES_IN_DAYS,
  inviteFormOptions,
  inviteFormSchema,
} from '@/features/admin/invite-form-schema'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

export function CreateInviteForm() {
  const createInvite = useCreateInvite()
  // The link is also in the mutation's data, so closing the dialog drops both
  const [inviteUrl, setInviteUrl] = useState<string | null>(null)

  const form = useAppForm({
    ...inviteFormOptions,
    onSubmit: async ({ value, formApi }) => {
      // Create the invite, show its link, then clear the form
      try {
        const newInviteUrl = await createInvite.mutateAsync(inviteFormSchema.parse(value))
        setInviteUrl(newInviteUrl)
        formApi.reset()
      } catch (error) {
        if (!isSessionEndedError(error)) {
          toast.error(apiErrorMessage(error))
        }
      }
    },
  })

  return (
    <SectionCard title="New invite">
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <form.AppField name="name">
          {(field) => (
            <field.TextField
              label="Name"
              description="Who the invite is for. Only admins see it."
            />
          )}
        </form.AppField>
        <form.AppField name="credit_amount_usd">
          {(field) => (
            <field.TextField
              label="Amount (USD)"
              description={`Credit given on sign-up. More than $0 and up to $${MAX_CREDIT_GRANT_USD}, to the cent.`}
            />
          )}
        </form.AppField>
        <form.AppField name="expires_in_days">
          {(field) => (
            <field.TextField
              label="Days until it expires"
              description={`1 to ${MAX_INVITE_EXPIRES_IN_DAYS} days.`}
            />
          )}
        </form.AppField>
        <form.AppField name="note">
          {(field) => <field.TextareaField label="Note (optional)" rows={3} />}
        </form.AppField>
        <form.AppForm>
          <form.SubmitButton label="Create invite" pendingLabel="Creating…" />
        </form.AppForm>
      </form>
      <InviteLinkDialog
        inviteUrl={inviteUrl}
        onClose={() => {
          setInviteUrl(null)
          createInvite.reset()
        }}
      />
    </SectionCard>
  )
}
