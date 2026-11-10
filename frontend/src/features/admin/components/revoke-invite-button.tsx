import { toast } from 'sonner'

import { ConfirmActionButton } from '@/components/confirm-action-button'
import { useRevokeInvite } from '@/features/admin/api/use-revoke-invite'
import { ApiError, apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type RevokeInviteButtonProps = {
  inviteIdentity: string
  inviteName: string
}

export function RevokeInviteButton({ inviteIdentity, inviteName }: RevokeInviteButtonProps) {
  const revokeInvite = useRevokeInvite()

  return (
    <ConfirmActionButton
      triggerLabel="Revoke"
      triggerVariant="ghost"
      triggerAriaLabel={`Revoke invite ${inviteName}`}
      title={`Revoke ${inviteName}?`}
      description="Its link stops working. This can't be undone."
      actionLabel="Revoke"
      isPending={revokeInvite.isPending}
      onConfirm={(close) =>
        revokeInvite.mutate(inviteIdentity, {
          onSuccess: () => {
            toast.success('Invite revoked')
            close()
          },
          onError: (error) => {
            if (isSessionEndedError(error)) {
              return
            }
            // A 409 means it was used first; the refreshed table shows it as used
            if (error instanceof ApiError && error.status === 409) {
              toast.error(
                typeof error.detail === 'string'
                  ? error.detail
                  : 'This invite was used before it could be revoked.',
              )
              close()
              return
            }
            toast.error(apiErrorMessage(error))
          },
        })
      }
    />
  )
}
