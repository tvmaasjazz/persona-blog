import { toast } from 'sonner'

import { ConfirmActionButton } from '@/components/confirm-action-button'
import { SectionCard } from '@/components/section-card'
import { useSetUserRole } from '@/features/admin/api/use-set-user-role'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type UserRoleControlProps = {
  userIdentity: string
  userEmail: string
  isCreator: boolean
}

export function UserRoleControl({ userIdentity, userEmail, isCreator }: UserRoleControlProps) {
  const setUserRole = useSetUserRole(userIdentity)
  const nextRole = isCreator ? 'READER' : 'CREATOR'
  const nextRoleLabel = isCreator ? 'reader' : 'creator'

  return (
    <SectionCard title="Role">
      <p className="text-muted-foreground">This user is a {isCreator ? 'creator' : 'reader'}.</p>
      <ConfirmActionButton
        triggerLabel={`Make ${nextRoleLabel}`}
        triggerVariant="secondary"
        title={`Make ${userEmail} a ${nextRoleLabel}?`}
        description={`They are signed out everywhere.${isCreator ? " Any runs they haven't finished fail." : ''}`}
        actionLabel={`Make ${nextRoleLabel}`}
        actionVariant="default"
        isPending={setUserRole.isPending}
        onConfirm={(close) =>
          setUserRole.mutate(
            { role: nextRole },
            {
              onSuccess: () => {
                toast.success(`Role changed to ${nextRoleLabel}`)
                close()
              },
              onError: (error) => {
                if (!isSessionEndedError(error)) {
                  toast.error(apiErrorMessage(error))
                }
              },
            },
          )
        }
      />
    </SectionCard>
  )
}
