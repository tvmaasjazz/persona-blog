import type { ComponentProps, ReactNode } from 'react'
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

type ButtonVariant = ComponentProps<typeof Button>['variant']

type ConfirmActionButtonProps = {
  triggerLabel: ReactNode
  triggerVariant: ButtonVariant
  triggerAriaLabel?: string
  title: ReactNode
  description: ReactNode
  actionLabel: string
  actionVariant?: ButtonVariant
  cancelLabel?: string
  isPending?: boolean
  // Runs on confirm; call close() on success so the dialog stays open on failure
  onConfirm: (close: () => void) => void
}

type OpenedText = {
  title: ReactNode
  description: ReactNode
  actionLabel: string
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
  const [openedText, setOpenedText] = useState<OpenedText>({ title, description, actionLabel })

  // Keep the text the dialog opened with, so it doesn't change while it fades out
  function handleOpenChange(isNextOpen: boolean) {
    if (isNextOpen) {
      setOpenedText({ title, description, actionLabel })
    }
    setIsOpen(isNextOpen)
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={handleOpenChange}>
      <AlertDialogTrigger asChild>
        <Button type="button" variant={triggerVariant} aria-label={triggerAriaLabel}>
          {triggerLabel}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="wrap-anywhere">{openedText.title}</AlertDialogTitle>
          <AlertDialogDescription>{openedText.description}</AlertDialogDescription>
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
            {openedText.actionLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
