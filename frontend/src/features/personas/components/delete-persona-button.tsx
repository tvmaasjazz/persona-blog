import { Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { ConfirmActionButton } from '@/components/confirm-action-button'
import { useDeletePersona } from '@/features/personas/api/use-delete-persona'
import { apiErrorMessage, isSessionEndedError } from '@/lib/api-error'

type DeletePersonaButtonProps = {
  personaIdentity: string
  personaName: string
}

export function DeletePersonaButton({ personaIdentity, personaName }: DeletePersonaButtonProps) {
  // Confirm, then delete and go to the list
  const navigate = useNavigate()
  const deletePersona = useDeletePersona()

  return (
    <ConfirmActionButton
      triggerLabel={
        <>
          <Trash2 aria-hidden />
          Delete
        </>
      }
      triggerVariant="ghost"
      triggerAriaLabel={`Delete ${personaName}`}
      title={`Delete ${personaName}?`}
      description="This persona will be removed from your list. This can't be undone."
      actionLabel="Delete persona"
      isPending={deletePersona.isPending}
      onConfirm={() =>
        deletePersona.mutate(personaIdentity, {
          onSuccess: () => {
            toast.success('Persona deleted')
            navigate('/personas')
          },
          onError: (error) => {
            if (!isSessionEndedError(error)) {
              toast.error(apiErrorMessage(error))
            }
          },
        })
      }
    />
  )
}
