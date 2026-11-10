import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/api-error'

const UNAUTHORIZED_STATUS = 401

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A query function returns signed-out state rather than throwing, so a failure is a
      // real error and retrying it only delays the message. The one exception is a 401:
      // the API cleared the deleted session's cookie with it, so one retry goes out signed
      // out, and an open route then succeeds.
      retry: (failureCount, error) =>
        failureCount < 1 && error instanceof ApiError && error.status === UNAUTHORIZED_STATUS,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
