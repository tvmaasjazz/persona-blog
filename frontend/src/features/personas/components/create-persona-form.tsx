import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { setFieldServerError } from '@/components/form/form-errors'
import { useAppForm } from '@/components/form/use-app-form'
import { useCreatePersona } from '@/features/personas/api/use-create-persona'
import { PersonaForm } from '@/features/personas/components/persona-form'
import { personaFormOptions, personaFormSchema } from '@/features/personas/persona-form-schema'
import { ApiError, apiErrorMessage } from '@/lib/api-error'

export function CreatePersonaForm() {
  // Empty form
  const navigate = useNavigate()
  const createPersona = useCreatePersona()

  const form = useAppForm({
    ...personaFormOptions,
    onSubmit: async ({ value, formApi }) => {
      // Create, then go to the persona; a name clash shows on the field
      try {
        const personaIdentity = await createPersona.mutateAsync(personaFormSchema.parse(value))
        toast.success('Persona created')
        navigate(`/personas/${personaIdentity}`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          setFieldServerError(formApi, 'name', apiErrorMessage(error))
        } else {
          toast.error(apiErrorMessage(error))
        }
      }
    },
  })

  return (
    <PersonaForm form={form} submitLabel="Create persona" onCancel={() => navigate('/personas')} />
  )
}
