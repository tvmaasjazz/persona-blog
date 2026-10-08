import { useParams } from 'react-router'

import { PersonaProfile } from '@/features/personas/components/persona-profile'

export function PersonaPage() {
  const { personaIdentity } = useParams()

  if (!personaIdentity) {
    return null
  }

  return <PersonaProfile personaIdentity={personaIdentity} />
}
