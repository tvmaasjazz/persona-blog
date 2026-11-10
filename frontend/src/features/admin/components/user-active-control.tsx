import { toast } from 'sonner'

import { ConfirmActionButton } from '@/components/confirm-action-button'
import { useSetUserActive } from '@/features/admin/api/use-set-user-active'
import { SectionCard } from '@/features/admin/components/section-card'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type UserActiveControlProps = {
  userIdentity: string
  userEmail: string
  isActive: boolean
}

export function UserActiveControl({ userIdentity, userEmail, isActive }: UserActiveControlProps) {
  const setUserActive = useSetUserActive(userIdentity)
  const actionLabel = isActive ? 'Suspend' : 'Reactivate'

  return (
    <SectionCard title="Access">
      <p className="text-muted-foreground">
        {isActive ? 'This account is active.' : 'This account is suspended.'}
      </p>
      <ConfirmActionButton
        triggerLabel={actionLabel}
        triggerVariant={isActive ? 'destructive' : 'secondary'}
        title={`${actionLabel} ${userEmail}?`}
        description={
          isActive
            ? "They are signed out everywhere and can't sign in until reactivated. Any runs they haven't finished fail."
            : 'They can sign in again.'
        }
        actionLabel={actionLabel}
        actionVariant={isActive ? 'destructive' : 'default'}
        isPending={setUserActive.isPending}
        onConfirm={(close) =>
          setUserActive.mutate(
            { is_active: !isActive },
            {
              onSuccess: () => {
                toast.success(isActive ? 'User suspended' : 'User reactivated')
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
