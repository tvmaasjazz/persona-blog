import { Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
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
import { useDeletePersona } from '@/features/personas/api/use-delete-persona'
import { apiErrorMessage } from '@/lib/api-error'

type DeletePersonaButtonProps = {
  personaIdentity: string
  personaName: string
}

export function DeletePersonaButton({ personaIdentity, personaName }: DeletePersonaButtonProps) {
  const navigate = useNavigate()
  const deletePersona = useDeletePersona()

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" aria-label={`Delete ${personaName}`}>
          <Trash2 aria-hidden />
          Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {personaName}?</AlertDialogTitle>
          <AlertDialogDescription>
            This persona will be removed from your list. This can't be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={deletePersona.isPending}
            onClick={(event) => {
              event.preventDefault()
              deletePersona.mutate(personaIdentity, {
                onSuccess: () => {
                  toast.success('Persona deleted')
                  navigate('/personas')
                },
                onError: (error) => toast.error(apiErrorMessage(error)),
              })
            }}
          >
            Delete persona
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
