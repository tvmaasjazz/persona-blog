import type { ReactNode } from 'react'
import { useState } from 'react'

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

type ButtonVariant = React.ComponentProps<typeof Button>['variant']
type ActionVariant = React.ComponentProps<typeof AlertDialogAction>['variant']

type ConfirmActionButtonProps = {
  triggerLabel: ReactNode
  triggerVariant: ButtonVariant
  triggerAriaLabel?: string
  title: ReactNode
  description: ReactNode
  actionLabel: string
  actionVariant?: ActionVariant
  cancelLabel?: string
  isPending?: boolean
  // Runs on confirm; call close() on success so the dialog stays open on failure
  onConfirm: (close: () => void) => void
}

// A button that asks in a dialog before running a destructive or far-reaching action.
export function ConfirmActionButton({
  triggerLabel,
  triggerVariant,
  triggerAriaLabel,
  title,
  description,
  actionLabel,
  actionVariant = 'destructive',
  cancelLabel = 'Cancel',
  isPending = false,
  onConfirm,
}: ConfirmActionButtonProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <AlertDialog open={isOpen} onOpenChange={setIsOpen}>
      <AlertDialogTrigger asChild>
        <Button type="button" variant={triggerVariant} aria-label={triggerAriaLabel}>
          {triggerLabel}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            variant={actionVariant}
            disabled={isPending}
            onClick={(event) => {
              // Keep the dialog open until onConfirm closes it
              event.preventDefault()
              onConfirm(() => setIsOpen(false))
            }}
          >
            {actionLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
