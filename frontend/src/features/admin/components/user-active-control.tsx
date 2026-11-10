import { toast } from 'sonner'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useSetUserActive } from '@/features/admin/api/use-set-user-active'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type UserActiveControlProps = {
  userIdentity: string
  userEmail: string
  isActive: boolean
  isOwnAccount: boolean
}

export function UserActiveControl({
  userIdentity,
  userEmail,
  isActive,
  isOwnAccount,
}: UserActiveControlProps) {
  const setUserActive = useSetUserActive(userIdentity, isOwnAccount)
  const actionLabel = isActive ? 'Suspend' : 'Reactivate'

  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <h2 className="text-xl font-extrabold">Access</h2>
      <p className="text-muted-foreground">
        {isActive ? 'This account is active.' : 'This account is suspended.'}
      </p>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant={isActive ? 'destructive' : 'secondary'}>{actionLabel}</Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {actionLabel} {userEmail}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {isActive
                ? "They are signed out everywhere and can't sign in until reactivated."
                : 'They are signed out everywhere, and can sign in again.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant={isActive ? 'destructive' : 'default'}
              disabled={setUserActive.isPending}
              onClick={(event) => {
                event.preventDefault()
                setUserActive.mutate(
                  { is_active: !isActive },
                  {
                    onSuccess: () =>
                      toast.success(isActive ? 'User suspended' : 'User reactivated'),
                    onError: (error) => {
                      if (!isSessionEndedError(error)) {
                        toast.error(apiErrorMessage(error))
                      }
                    },
                  },
                )
              }}
            >
              {actionLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
