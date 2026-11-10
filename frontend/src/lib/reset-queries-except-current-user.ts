import type { QueryClient } from '@tanstack/react-query'

// Resets every query but ['users', 'me'], so an open page refetches as whoever is asking now.
export function resetQueriesExceptCurrentUser(queryClient: QueryClient) {
  return queryClient.resetQueries({
    predicate: (query) => !(query.queryKey[0] === 'users' && query.queryKey[1] === 'me'),
  })
}
