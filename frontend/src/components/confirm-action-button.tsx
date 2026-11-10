import type { ComponentProps, ReactNode } from 'react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
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

// A button that asks in a dialog before running a destructive or far-reaching action.
export function ConfirmActionButton({
  triggerLabel,
  triggerVariant,
  triggerAriaLabel,
  onConfirm,
  ...dialogProps
}: ConfirmActionButtonProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <ConfirmDialog
      {...dialogProps}
      trigger={
        <Button type="button" variant={triggerVariant} aria-label={triggerAriaLabel}>
          {triggerLabel}
        </Button>
      }
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      onConfirm={() => onConfirm(() => setIsOpen(false))}
    />
  )
}
