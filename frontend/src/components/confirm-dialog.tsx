import type { ComponentProps, ReactNode, RefObject } from 'react'
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
import type { Button } from '@/components/ui/button'

type ButtonVariant = ComponentProps<typeof Button>['variant']

type ConfirmDialogProps = {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  title: ReactNode
  description: ReactNode
  actionLabel: string
  actionVariant?: ButtonVariant
  cancelLabel?: string
  isPending?: boolean
  // The button that opens the dialog, so focus returns to it on close
  trigger?: ReactNode
  // Where focus goes on close when there is no trigger
  returnFocusRef?: RefObject<HTMLElement | null>
  // The dialog stays open until the caller closes it
  onConfirm: () => void
}

type OpenedText = {
  title: ReactNode
  description: ReactNode
  actionLabel: string
}

// A dialog that asks before a destructive or far-reaching action runs.
export function ConfirmDialog({
  isOpen,
  onOpenChange,
  title,
  description,
  actionLabel,
  actionVariant = 'destructive',
  cancelLabel = 'Cancel',
  isPending = false,
  trigger,
  returnFocusRef,
  onConfirm,
}: ConfirmDialogProps) {
  const [openedText, setOpenedText] = useState<OpenedText>({ title, description, actionLabel })
  const [wasOpen, setWasOpen] = useState(isOpen)

  // Keep the text the dialog opened with, so it doesn't change while it fades out
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen)
    if (isOpen) {
      setOpenedText({ title, description, actionLabel })
    }
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={onOpenChange}>
      {trigger && <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>}
      <AlertDialogContent
        onCloseAutoFocus={(event) => {
          if (returnFocusRef?.current) {
            event.preventDefault()
            returnFocusRef.current.focus()
          }
        }}
      >
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
              // Keep the dialog open until the caller closes it
              event.preventDefault()
              onConfirm()
            }}
          >
            {openedText.actionLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
