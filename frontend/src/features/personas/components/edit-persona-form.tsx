import type { AnyFormApi } from '@tanstack/react-form'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import type { z } from 'zod'

import { setFieldServerError } from '@/components/form/form-errors'
import { useAppForm } from '@/components/form/use-app-form'
import { QueryErrorState } from '@/components/query-error-state'
import { usePersona } from '@/features/personas/api/persona-query'
import { useUpdatePersona } from '@/features/personas/api/use-update-persona'
import { MakePersonaPrivateDialog } from '@/features/personas/components/make-persona-private-dialog'
import { PersonaForm } from '@/features/personas/components/persona-form'
import {
  personaFormOptions,
  personaFormSchema,
  toPersonaFormValues,
} from '@/features/personas/persona-form-schema'
import { ApiError, apiErrorMessage, isSessionEndedError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type PersonaFormValues = z.input<typeof personaFormSchema>
type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type EditPersonaFormProps = {
  personaIdentity: string
  // Public posts the persona has, from the route; undefined while it loads
  publicPostCount: number | undefined
}

export function EditPersonaForm({ personaIdentity, publicPostCount }: EditPersonaFormProps) {
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

  return <LoadedEditPersonaForm persona={persona} publicPostCount={publicPostCount} />
}

type LoadedEditPersonaFormProps = {
  persona: PersonaResponseDto
  publicPostCount: number | undefined
}

// Split out so the form starts from the loaded persona.
function LoadedEditPersonaForm({ persona, publicPostCount }: LoadedEditPersonaFormProps) {
  // Form starting from the persona
  const navigate = useNavigate()
  const updatePersona = useUpdatePersona()
  const [isConfirmOpen, setIsConfirmOpen] = useState(false)

  const form = useAppForm({
    ...personaFormOptions,
    defaultValues: toPersonaFormValues(persona),
    onSubmit: async ({ value, formApi }) => {
      // Ask first when this may hide public posts, including when the count is unknown
      const isHidingPosts = persona.is_public && !value.is_public && publicPostCount !== 0
      if (isHidingPosts) {
        setIsConfirmOpen(true)
        return
      }

      await savePersona(value, formApi)
    },
  })

  // Save, then go to the persona; a name clash shows on the field
  async function savePersona(value: PersonaFormValues, formApi: AnyFormApi) {
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
  }

  async function handleConfirm() {
    // Save, then close; a failure shows on the form behind the dialog
    await savePersona(form.state.values, form)
    setIsConfirmOpen(false)
  }

  return (
    <>
      <PersonaForm
        form={form}
        submitLabel="Save changes"
        onCancel={() => navigate(`/personas/${persona.identity}`)}
      />
      <MakePersonaPrivateDialog
        isOpen={isConfirmOpen}
        onOpenChange={setIsConfirmOpen}
        personaName={persona.name}
        publicPostCount={publicPostCount}
        isPending={updatePersona.isPending}
        onConfirm={handleConfirm}
      />
    </>
  )
}
