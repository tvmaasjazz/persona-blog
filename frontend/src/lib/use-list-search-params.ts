import { useSearchParams } from 'react-router'

import type { components } from '@/lib/api-schema.gen'

type SortDirection = components['schemas']['SortDirectionType']

const SORT_DIRECTIONS = ['ASC', 'DESC'] as const

type ListSortOptions<TSort extends string> = {
  sortValues: readonly TSort[]
  defaultSort: TSort
  defaultDirection: SortDirection
}

type ListSearchParams = {
  page: number
  search: string
  setPage: (nextPage: number) => void
  setSearch: (nextSearch: string) => void
  setFilter: (name: string, value: string | null) => void
}

type ListSortParams<TSort extends string> = {
  sortBy: TSort
  sortDirection: SortDirection
  setSort: (nextSort: TSort, nextDirection: SortDirection) => void
}

// Reads and writes page, q, sort and dir, plus any named filter, in the URL, leaving other params alone.
// A list with one order passes no sort options, and gets no sort back.
export function useListSearchParams(): ListSearchParams
export function useListSearchParams<TSort extends string>(
  sortOptions: ListSortOptions<TSort>,
): ListSearchParams & ListSortParams<TSort>
export function useListSearchParams<TSort extends string>(
  sortOptions?: ListSortOptions<TSort>,
): ListSearchParams & Partial<ListSortParams<TSort>> {
  const [searchParams, setSearchParams] = useSearchParams()

  // Read each value, falling back when the URL holds something invalid
  const pageNumber = Number(searchParams.get('page'))
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber : 1
  const search = searchParams.get('q') ?? ''

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

  function setFilter(name: string, value: string | null) {
    writeParams({ [name]: value, page: null }, { replace: true })
  }

  const listSearchParams = { page, search, setPage, setSearch, setFilter }
  if (!sortOptions) {
    return listSearchParams
  }

  // Read the sort, falling back when the URL holds something invalid
  const { sortValues, defaultSort, defaultDirection } = sortOptions
  const sortParam = searchParams.get('sort')
  const sortBy = sortValues.find((value) => value === sortParam) ?? defaultSort
  const directionParam = searchParams.get('dir')
  const sortDirection =
    SORT_DIRECTIONS.find((direction) => direction === directionParam) ?? defaultDirection

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

  return { ...listSearchParams, sortBy, sortDirection, setSort }
}
