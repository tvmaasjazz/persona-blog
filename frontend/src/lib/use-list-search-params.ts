import { useSearchParams } from 'react-router'

type UseListSearchParamsOptions<TSort extends string> = {
  sortValues: readonly TSort[]
  defaultSort: TSort
  defaultDirection: 'ASC' | 'DESC'
}

// Reads and writes page, q, sort and dir in the URL, leaving any other param alone.
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
  const sortDirection: 'ASC' | 'DESC' =
    searchParams.get('dir') === 'ASC' || searchParams.get('dir') === 'DESC'
      ? (searchParams.get('dir') as 'ASC' | 'DESC')
      : defaultDirection

  // Write one param, or remove it when it equals its default
  function writeParams(changes: Record<string, string | null>) {
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
    })
  }

  function setPage(nextPage: number) {
    writeParams({ page: nextPage <= 1 ? null : String(nextPage) })
  }

  function setSearch(nextSearch: string) {
    writeParams({ q: nextSearch === '' ? null : nextSearch, page: null })
  }

  function setSort(nextSort: TSort, nextDirection: 'ASC' | 'DESC') {
    writeParams({
      sort: nextSort === defaultSort ? null : nextSort,
      dir: nextDirection === defaultDirection ? null : nextDirection,
      page: null,
    })
  }

  return { page, search, sortBy, sortDirection, setPage, setSearch, setSort }
}
