import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { setFieldServerError } from '@/components/form/form-errors'
import { useAppForm } from '@/components/form/use-app-form'
import { QueryErrorState } from '@/components/query-error-state'
import { usePersona } from '@/features/personas/api/persona-query'
import { useUpdatePersona } from '@/features/personas/api/use-update-persona'
import { PersonaForm } from '@/features/personas/components/persona-form'
import {
  personaFormOptions,
  personaFormSchema,
  toPersonaFormValues,
} from '@/features/personas/persona-form-schema'
import { ApiError, apiErrorMessage, isSessionEndedError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type EditPersonaFormProps = {
  personaIdentity: string
}

export function EditPersonaForm({ personaIdentity }: EditPersonaFormProps) {
  // Load the persona
  const { data: persona, isPending, error } = usePersona(personaIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  // Not found or failed
  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Persona not found."
        backTo={{ to: '/personas', label: 'Back to personas' }}
      />
    )
  }

  return <LoadedEditPersonaForm persona={persona} />
}

type LoadedEditPersonaFormProps = {
  persona: PersonaResponseDto
}

// Split out so the form starts from the loaded persona.
function LoadedEditPersonaForm({ persona }: LoadedEditPersonaFormProps) {
  // Form starting from the persona
  const navigate = useNavigate()
  const updatePersona = useUpdatePersona()

  const form = useAppForm({
    ...personaFormOptions,
    defaultValues: toPersonaFormValues(persona),
    onSubmit: async ({ value, formApi }) => {
      // Save, then go to the persona; a name clash shows on the field
      try {
        await updatePersona.mutateAsync({
          personaIdentity: persona.identity,
          persona: personaFormSchema.parse(value),
        })
        toast.success('Persona saved')
        navigate(`/personas/${persona.identity}`)
      } catch (error) {
        if (isSessionEndedError(error)) {
          return
        }
        if (error instanceof ApiError && error.status === 409) {
          setFieldServerError(formApi, 'name', apiErrorMessage(error))
        } else {
          toast.error(apiErrorMessage(error))
        }
      }
    },
  })

  return (
    <PersonaForm
      form={form}
      submitLabel="Save changes"
      onCancel={() => navigate(`/personas/${persona.identity}`)}
    />
  )
}
