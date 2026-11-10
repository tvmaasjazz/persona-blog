import { Trash2 } from 'lucide-react'

import { ConfirmActionButton } from '@/components/confirm-action-button'

type DiscardRunButtonProps = {
  onDiscard: () => void
}

// Confirms before discarding an unsaved post; sends nothing.
export function DiscardRunButton({ onDiscard }: DiscardRunButtonProps) {
  return (
    <ConfirmActionButton
      triggerLabel={
        <>
          <Trash2 aria-hidden />
          Discard
        </>
      }
      triggerVariant="ghost"
      title="Discard this post?"
      description="It won't be saved to your posts, and you won't be able to come back to it."
      actionLabel="Discard post"
      cancelLabel="Keep it"
      onConfirm={(close) => {
        onDiscard()
        close()
      }}
    />
  )
}
