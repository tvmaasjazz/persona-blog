import { useParams } from 'react-router'

import { EditPersonaForm } from '@/features/personas/components/edit-persona-form'

export function EditPersonaPage() {
  const { personaIdentity } = useParams()

  if (!personaIdentity) {
    return null
  }

  return (
    <>
      <h1 className="mb-6 text-xl font-extrabold">Edit persona</h1>
      <EditPersonaForm personaIdentity={personaIdentity} />
    </>
  )
}
