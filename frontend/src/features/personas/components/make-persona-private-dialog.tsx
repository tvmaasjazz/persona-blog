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

type MakePersonaPrivateDialogProps = {
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  personaName: string
  publicPostCount: number
  isPending: boolean
  onConfirm: () => void
}

// Warns that making a persona private hides its public posts.
export function MakePersonaPrivateDialog({
  isOpen,
  onOpenChange,
  personaName,
  publicPostCount,
  isPending,
  onConfirm,
}: MakePersonaPrivateDialogProps) {
  const postsLabel = publicPostCount === 1 ? '1 public post' : `${publicPostCount} public posts`

  return (
    <AlertDialog open={isOpen} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="wrap-anywhere">Make {personaName} private?</AlertDialogTitle>
          <AlertDialogDescription>
            Its {postsLabel} will be hidden until the persona is public again.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={isPending}
            onClick={(event) => {
              // Keep the dialog open until the save finishes
              event.preventDefault()
              onConfirm()
            }}
          >
            Make private
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
