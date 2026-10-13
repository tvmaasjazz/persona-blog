import type { Blocker } from 'react-router'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

type LeaveUnsavedRunDialogProps = {
  blocker: Blocker
}

export function LeaveUnsavedRunDialog({ blocker }: LeaveUnsavedRunDialogProps) {
  return (
    <AlertDialog
      open={blocker.state === 'blocked'}
      onOpenChange={(isOpen) => {
        if (!isOpen && blocker.state === 'blocked') {
          blocker.reset()
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
          <AlertDialogDescription>
            This post isn't saved yet. If you leave, you won't be able to come back to it.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Stay</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              if (blocker.state === 'blocked') {
                blocker.proceed()
              }
            }}
          >
            Leave
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
