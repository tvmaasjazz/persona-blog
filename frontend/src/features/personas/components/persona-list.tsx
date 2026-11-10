import { Link } from 'react-router'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { ListPager } from '@/components/list-pager'
import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { PersonaCard } from '@/features/personas/components/persona-card'
import type { components } from '@/lib/api-schema.gen'

type UserPersonaPageResponseDto = components['schemas']['UserPersonaPageResponseDto']

type PersonaListProps = {
  page: UserPersonaPageResponseDto | undefined
  error: Error | null
  search: string
  onPageChange: (page: number) => void
}

export function PersonaList({ page, error, search, onPageChange }: PersonaListProps) {
  if (error) {
    return <QueryErrorState error={error} notFoundMessage="Personas not found." />
  }

  if (!page) {
    return <CardListSkeleton />
  }

  // No match for the search, which differs from having no personas
  if (page.personas.length === 0 && search) {
    return <p className="text-muted-foreground">No personas match "{search}".</p>
  }

  if (page.personas.length === 0) {
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

  // One card per persona, then the pager
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        {page.personas.map((persona) => (
          <PersonaCard key={persona.identity} persona={persona} />
        ))}
      </div>
      <ListPager pagination={page.pagination} onPageChange={onPageChange} />
    </div>
  )
}
