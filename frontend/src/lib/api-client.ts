import createClient from 'openapi-fetch'
import { toast } from 'sonner'

import { queryClient } from '@/app/query-client'
import type { paths } from '@/lib/api-schema.gen'

// A 401 from these says nothing new: /users/me reads signed out as null, and signing out
// with a session the server already deleted is the outcome the user asked for
const QUIET_UNAUTHORIZED_PATHS = new Set(['/api/users/me', '/api/auth/logout'])
const CURRENT_USER_QUERY_KEY = ['users', 'me']

export const apiClient = createClient<paths>({ baseUrl: '/api' })

// A 401 from any other route means the server deleted the session (a grant, a role
// change, a suspension), and the API has already cleared its cookie: show the app
// signed out, and say so once.
apiClient.use({
  onResponse({ request, response }) {
    if (response.status !== 401 || QUIET_UNAUTHORIZED_PATHS.has(new URL(request.url).pathname)) {
      return undefined
    }

    if (queryClient.getQueryData(CURRENT_USER_QUERY_KEY)) {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null)
      toast.error('You were signed out. Sign in again.')
    }

    return undefined
  },
})
