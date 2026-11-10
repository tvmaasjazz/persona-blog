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
import { useSetUserRole } from '@/features/admin/api/use-set-user-role'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type UserRoleControlProps = {
  userIdentity: string
  userEmail: string
  isCreator: boolean
  isOwnAccount: boolean
}

export function UserRoleControl({
  userIdentity,
  userEmail,
  isCreator,
  isOwnAccount,
}: UserRoleControlProps) {
  const setUserRole = useSetUserRole(userIdentity, isOwnAccount)
  const nextRole = isCreator ? 'READER' : 'CREATOR'
  const nextRoleLabel = isCreator ? 'reader' : 'creator'

  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <h2 className="text-xl font-extrabold">Role</h2>
      <p className="text-muted-foreground">This user is a {isCreator ? 'creator' : 'reader'}.</p>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="secondary">Make {nextRoleLabel}</Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Make {userEmail} a {nextRoleLabel}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              They are signed out everywhere.
              {isCreator && " Any runs they haven't finished fail."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={setUserRole.isPending}
              onClick={(event) => {
                event.preventDefault()
                setUserRole.mutate(
                  { role: nextRole },
                  {
                    onSuccess: () => toast.success(`Role changed to ${nextRoleLabel}`),
                    onError: (error) => {
                      if (!isSessionEndedError(error)) {
                        toast.error(apiErrorMessage(error))
                      }
                    },
                  },
                )
              }}
            >
              Make {nextRoleLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
