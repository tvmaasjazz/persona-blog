import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

type InviteLinkDialogProps = {
  // The link to show, or null while the dialog is closed
  inviteUrl: string | null
  onClose: () => void
}

// Shows a new invite's link once; the parent drops the link when this closes.
export function InviteLinkDialog({ inviteUrl, onClose }: InviteLinkDialogProps) {
  const [isCopied, setIsCopied] = useState(false)

  // Copy the link, then confirm
  async function handleCopy() {
    if (inviteUrl === null) {
      return
    }
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setIsCopied(true)
    } catch {
      toast.error("Couldn't copy the link. Select it and copy it by hand.")
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) {
      setIsCopied(false)
      onClose()
    }
  }

  return (
    <Dialog open={inviteUrl !== null} onOpenChange={handleOpenChange}>
      {/* A stray click outside would lose the link for good */}
      <DialogContent onInteractOutside={(event) => event.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Invite link</DialogTitle>
          <DialogDescription>
            Copy this link now. It can't be shown again once you close this.
          </DialogDescription>
        </DialogHeader>
        <Input
          readOnly
          aria-label="Invite link"
          value={inviteUrl ?? ''}
          onFocus={(event) => event.target.select()}
        />
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
            Close
          </Button>
          <Button type="button" onClick={() => void handleCopy()}>
            <span aria-live="polite">{isCopied ? 'Copied' : 'Copy link'}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
