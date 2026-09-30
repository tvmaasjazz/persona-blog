import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { setFieldServerError } from '@/components/form/form-errors'
import { useAppForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
import { usePersona } from '@/features/personas/api/persona-query'
import { useUpdatePersona } from '@/features/personas/api/use-update-persona'
import { PersonaForm } from '@/features/personas/components/persona-form'
import {
  personaFormOptions,
  personaFormSchema,
  toPersonaFormValues,
} from '@/features/personas/persona-form-schema'
import { ApiError, apiErrorMessage } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type EditPersonaFormProps = {
  personaIdentity: string
}

export function EditPersonaForm({ personaIdentity }: EditPersonaFormProps) {
  const { data: persona, isPending, error } = usePersona(personaIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-muted-foreground">
          {isNotFound ? 'Persona not found' : apiErrorMessage(error)}
        </p>
        <Button asChild variant="secondary">
          <Link to="/personas">Back to personas</Link>
        </Button>
      </div>
    )
  }

  return <LoadedEditPersonaForm persona={persona} />
}

type LoadedEditPersonaFormProps = {
  persona: PersonaResponseDto
}

// Split out so useAppForm starts from the loaded persona.
function LoadedEditPersonaForm({ persona }: LoadedEditPersonaFormProps) {
  const navigate = useNavigate()
  const updatePersona = useUpdatePersona()

  const form = useAppForm({
    ...personaFormOptions,
    defaultValues: toPersonaFormValues(persona),
    onSubmit: async ({ value, formApi }) => {
      try {
        await updatePersona.mutateAsync({
          personaIdentity: persona.identity,
          persona: personaFormSchema.parse(value),
        })
        toast.success('Persona saved')
        navigate(`/personas/${persona.identity}`)
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
    <PersonaForm
      form={form}
      submitLabel="Save changes"
      onCancel={() => navigate(`/personas/${persona.identity}`)}
    />
  )
}
