import { useSearchParams } from 'react-router'

import type { components } from '@/lib/api-schema.gen'

type SortDirection = components['schemas']['SortDirectionType']

const SORT_DIRECTIONS = ['ASC', 'DESC'] as const

type UseListSearchParamsOptions<TSort extends string> = {
  sortValues: readonly TSort[]
  defaultSort: TSort
  defaultDirection: SortDirection
}

// Reads and writes page, q, sort and dir, plus any named filter, in the URL, leaving other params alone.
export function useListSearchParams<TSort extends string>({
  sortValues,
  defaultSort,
  defaultDirection,
}: UseListSearchParamsOptions<TSort>) {
  const [searchParams, setSearchParams] = useSearchParams()

  // Read each value, falling back when the URL holds something invalid
  const pageNumber = Number(searchParams.get('page'))
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber : 1
  const search = searchParams.get('q') ?? ''
  const sortParam = searchParams.get('sort')
  const sortBy = sortValues.find((value) => value === sortParam) ?? defaultSort
  const directionParam = searchParams.get('dir')
  const sortDirection =
    SORT_DIRECTIONS.find((direction) => direction === directionParam) ?? defaultDirection

  // Write params, or remove one set to null
  function writeParams(changes: Record<string, string | null>, options: { replace: boolean }) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      for (const [key, value] of Object.entries(changes)) {
        if (value === null) {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      }
      return next
    }, options)
  }

  // A page change is a step in history; the rest refine the list in place
  function setPage(nextPage: number) {
    writeParams({ page: nextPage <= 1 ? null : String(nextPage) }, { replace: false })
  }

  function setSearch(nextSearch: string) {
    writeParams({ q: nextSearch === '' ? null : nextSearch, page: null }, { replace: true })
  }

  function setSort(nextSort: TSort, nextDirection: SortDirection) {
    writeParams(
      {
        sort: nextSort === defaultSort ? null : nextSort,
        dir: nextDirection === defaultDirection ? null : nextDirection,
        page: null,
      },
      { replace: true },
    )
  }

  function setFilter(name: string, value: string | null) {
    writeParams({ [name]: value, page: null }, { replace: true })
  }

  return { page, search, sortBy, sortDirection, setPage, setSearch, setSort, setFilter }
}
