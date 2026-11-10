import { Link } from 'react-router'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { PastLastPageNotice } from '@/components/past-last-page-notice'
import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { PersonaCard } from '@/features/personas/components/persona-card'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']
type PaginationResponseDto = components['schemas']['PaginationResponseDto']

type PersonaListProps = {
  personas: PersonaResponseDto[] | undefined
  isPending: boolean
  error: Error | null
  // A search is narrowing the list
  isNarrowed: boolean
  pagination: PaginationResponseDto | undefined
  onPageChange: (page: number) => void
}

export function PersonaList({
  personas,
  isPending,
  error,
  isNarrowed,
  pagination,
  onPageChange,
}: PersonaListProps) {
  if (isPending || !personas) {
    return error ? <QueryErrorState error={error} /> : <CardListSkeleton />
  }

  if (personas.length === 0) {
    // Past the last page, such as after a delete or a stale link
    if (pagination && pagination.total > 0) {
      return <PastLastPageNotice onFirstPage={() => onPageChange(1)} />
    }

    // No match for the search, which differs from having no personas
    if (isNarrowed) {
      return <p className="break-words text-muted-foreground">No personas match your search.</p>
    }

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
      {personas.map((persona) => (
        <PersonaCard key={persona.identity} persona={persona} />
      ))}
    </div>
  )
}
