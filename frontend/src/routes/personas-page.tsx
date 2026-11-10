import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import { ListPager } from '@/components/list-pager'
import { ListSearchBox } from '@/components/list-search-box'
import { Button } from '@/components/ui/button'
import { useUserPersonaPage } from '@/features/personas/api/user-persona-page-query'
import { PersonaList } from '@/features/personas/components/persona-list'
import type { components } from '@/lib/api-schema.gen'
import { useListSearchParams } from '@/lib/use-list-search-params'

const PAGE_SIZE = 20
const SORT_VALUES = [
  'CREATED_AT',
] as const satisfies readonly components['schemas']['UserPersonaSortType'][]

export function PersonasPage() {
  // Page and search live in the URL
  const { page, search, sortBy, sortDirection, setPage, setSearch } = useListSearchParams({
    sortValues: SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const {
    data: personaPage,
    isPending,
    error,
  } = useUserPersonaPage({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    sort_by: sortBy,
    sort_direction: sortDirection,
  })

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-extrabold">My Personas</h1>
        <Button asChild>
          <Link to="/personas/new">
            <Plus aria-hidden />
            New persona
          </Link>
        </Button>
      </div>
      <div className="mb-6">
        <ListSearchBox label="Search personas" value={search} onChange={setSearch} />
      </div>
      <PersonaList
        personas={personaPage?.personas}
        isPending={isPending}
        error={error}
        isNarrowed={search !== ''}
        pagination={personaPage?.pagination}
        onPageChange={setPage}
      />
      {personaPage && (
        <div className="mt-6">
          <ListPager pagination={personaPage.pagination} onPageChange={setPage} />
        </div>
      )}
    </>
  )
}
