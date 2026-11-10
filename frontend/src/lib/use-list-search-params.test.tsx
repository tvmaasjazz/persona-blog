// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation, useNavigationType } from 'react-router'
import { describe, expect, it } from 'vitest'

import { useListSearchParams } from '@/lib/use-list-search-params'

const SORT_VALUES = ['created_at', 'title'] as const

// Renders the hook at a URL, beside the location and how the router last got there
function renderListSearchParams(initialUrl: string) {
  function RouterWrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[initialUrl]}>{children}</MemoryRouter>
  }
  return renderHook(
    () => ({
      list: useListSearchParams({
        sortValues: SORT_VALUES,
        defaultSort: 'created_at',
        defaultDirection: 'DESC',
      }),
      location: useLocation(),
      navigationType: useNavigationType(),
    }),
    { wrapper: RouterWrapper },
  )
}

describe('useListSearchParams reading the URL', () => {
  it('reads page, search, sort and direction from the URL', () => {
    const { result } = renderListSearchParams('/posts?page=3&q=cats&sort=title&dir=ASC')

    expect(result.current.list.page).toBe(3)
    expect(result.current.list.search).toBe('cats')
    expect(result.current.list.sortBy).toBe('title')
    expect(result.current.list.sortDirection).toBe('ASC')
  })

  it('falls back to page 1, no search and the default sort when the URL has none', () => {
    const { result } = renderListSearchParams('/posts')

    expect(result.current.list.page).toBe(1)
    expect(result.current.list.search).toBe('')
    expect(result.current.list.sortBy).toBe('created_at')
    expect(result.current.list.sortDirection).toBe('DESC')
  })

  it.each(['abc', '0', '-3', '2.5', ''])('reads page=%j as page 1', (pageParam) => {
    const { result } = renderListSearchParams(`/posts?page=${pageParam}`)

    expect(result.current.list.page).toBe(1)
  })

  it('falls back to the default sort for a sort not in the allowed values', () => {
    const { result } = renderListSearchParams('/posts?sort=password_hash')

    expect(result.current.list.sortBy).toBe('created_at')
  })

  it('falls back to the default direction for a direction other than ASC or DESC', () => {
    const { result } = renderListSearchParams('/posts?dir=asc')

    expect(result.current.list.sortDirection).toBe('DESC')
  })
})

describe('useListSearchParams writing the URL', () => {
  it('writes the page, keeping the params it does not own', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&q=cats')

    act(() => result.current.list.setPage(4))

    expect(result.current.location.search).toBe('?tag=ai&q=cats&page=4')
    expect(result.current.list.page).toBe(4)
  })

  it('leaves page 1 out of the URL', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&page=4')

    act(() => result.current.list.setPage(1))

    expect(result.current.location.search).toBe('?tag=ai')
  })

  it('writes the search and returns to page 1, keeping the params it does not own', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&page=3')

    act(() => result.current.list.setSearch('cats'))

    expect(result.current.location.search).toBe('?tag=ai&q=cats')
    expect(result.current.list.page).toBe(1)
  })

  it('removes an emptied search from the URL', () => {
    const { result } = renderListSearchParams('/posts?q=cats')

    act(() => result.current.list.setSearch(''))

    expect(result.current.location.search).toBe('')
  })

  it('writes the sort and direction and returns to page 1, keeping the params it does not own', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&page=3')

    act(() => result.current.list.setSort('title', 'ASC'))

    expect(result.current.location.search).toBe('?tag=ai&sort=title&dir=ASC')
    expect(result.current.list.sortBy).toBe('title')
    expect(result.current.list.sortDirection).toBe('ASC')
  })

  it('removes the default sort and direction from the URL', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&sort=title&dir=ASC')

    act(() => result.current.list.setSort('created_at', 'DESC'))

    expect(result.current.location.search).toBe('?tag=ai')
  })

  it('keeps a non-default direction when the sort goes back to the default', () => {
    const { result } = renderListSearchParams('/posts?tag=ai&sort=title')

    act(() => result.current.list.setSort('created_at', 'ASC'))

    expect(result.current.location.search).toBe('?tag=ai&dir=ASC')
  })

  it('writes a filter and returns to page 1, keeping the params it does not own', () => {
    const { result } = renderListSearchParams('/posts?q=cats&page=3')

    act(() => result.current.list.setFilter('status', 'PENDING'))

    expect(result.current.location.search).toBe('?q=cats&status=PENDING')
  })

  it('removes a filter set to null and returns to page 1', () => {
    const { result } = renderListSearchParams('/posts?status=PENDING&q=cats&page=3')

    act(() => result.current.list.setFilter('status', null))

    expect(result.current.location.search).toBe('?q=cats')
  })
})

describe('useListSearchParams history', () => {
  it('pushes a history entry for a page change', () => {
    const { result } = renderListSearchParams('/posts')

    act(() => result.current.list.setPage(2))

    expect(result.current.navigationType).toBe('PUSH')
  })

  it('replaces the history entry for a search', () => {
    const { result } = renderListSearchParams('/posts')

    act(() => result.current.list.setSearch('cats'))

    expect(result.current.navigationType).toBe('REPLACE')
  })

  it('replaces the history entry for a sort', () => {
    const { result } = renderListSearchParams('/posts')

    act(() => result.current.list.setSort('title', 'ASC'))

    expect(result.current.navigationType).toBe('REPLACE')
  })

  it('replaces the history entry for a filter', () => {
    const { result } = renderListSearchParams('/posts')

    act(() => result.current.list.setFilter('status', 'PENDING'))

    expect(result.current.navigationType).toBe('REPLACE')
  })
})

describe('useListSearchParams without sort options', () => {
  it('reads page and search, and leaves a sort in the URL unread', () => {
    function RouterWrapper({ children }: { children: ReactNode }) {
      return <MemoryRouter initialEntries={['/?page=2&q=cats&sort=title']}>{children}</MemoryRouter>
    }
    const { result } = renderHook(() => useListSearchParams(), { wrapper: RouterWrapper })

    expect(result.current).toEqual({
      page: 2,
      search: 'cats',
      setPage: expect.any(Function),
      setSearch: expect.any(Function),
      setFilter: expect.any(Function),
    })
  })
})
