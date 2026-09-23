import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A query function returns signed-out state rather than throwing, so a
      // failure here is a real error and retrying it only delays the message.
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
