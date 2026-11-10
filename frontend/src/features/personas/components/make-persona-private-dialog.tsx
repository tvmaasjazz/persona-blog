import type { RefObject } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'

type MakePersonaPrivateDialogProps = {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  personaName: string
  // Undefined when the count is unknown
  publicPostCount: number | undefined
  isPending: boolean
  returnFocusRef: RefObject<HTMLElement | null>
  onConfirm: () => void
}

// Warns that making a persona private hides its public posts.
export function MakePersonaPrivateDialog({
  isOpen,
  onOpenChange,
  personaName,
  publicPostCount,
  isPending,
  returnFocusRef,
  onConfirm,
}: MakePersonaPrivateDialogProps) {
  let postsLabel = 'Its public posts'
  if (publicPostCount !== undefined) {
    postsLabel = publicPostCount === 1 ? 'Its 1 public post' : `Its ${publicPostCount} public posts`
  }

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Make ${personaName} private?`}
      description={`${postsLabel} will be hidden until the persona is public again.`}
      actionLabel="Make private"
      isPending={isPending}
      returnFocusRef={returnFocusRef}
      onConfirm={onConfirm}
    />
  )
}
