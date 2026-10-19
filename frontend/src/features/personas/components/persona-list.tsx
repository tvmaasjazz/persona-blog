import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { usePersonaList } from '@/features/personas/api/persona-list-query'
import { PersonaCard } from '@/features/personas/components/persona-card'

export function PersonaList() {
  // Load the personas
  const { data: personaList, isPending, isError } = usePersonaList()

  if (isPending) {
    return (
      <div className="flex flex-col gap-3">
        <div className="h-24 rounded-2xl bg-accent" />
        <div className="h-24 rounded-2xl bg-accent" />
        <div className="h-24 rounded-2xl bg-accent" />
      </div>
    )
  }

  // Failed or empty
  if (isError) {
    return <p className="text-muted-foreground">Couldn't load your personas. Try again.</p>
  }

  if (personaList.personas.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border bg-card p-6">
        <p className="text-muted-foreground">
          No personas yet. Create one to give your posts a voice.
        </p>
        <Button asChild>
          <Link to="/personas/new">Create a persona</Link>
        </Button>
      </div>
    )
  }

  // One card per persona
  return (
    <div className="flex flex-col gap-3">
      {personaList.personas.map((persona) => (
        <PersonaCard key={persona.identity} persona={persona} />
      ))}
    </div>
  )
}
