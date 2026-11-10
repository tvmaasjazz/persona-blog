import createClient from 'openapi-fetch'
import { toast } from 'sonner'

import { queryClient } from '@/app/query-client'
import type { paths } from '@/lib/api-schema.gen'

const CURRENT_USER_PATH = '/api/users/me'
const CURRENT_USER_QUERY_KEY = ['users', 'me']

export const apiClient = createClient<paths>({ baseUrl: '/api' })

// A 401 from any other route means the server deleted the session (a grant, a role
// change, a suspension), and the API has already cleared its cookie: show the app
// signed out, and say so once.
apiClient.use({
  onResponse({ request, response }) {
    if (response.status !== 401 || new URL(request.url).pathname === CURRENT_USER_PATH) {
      return undefined
    }

    if (queryClient.getQueryData(CURRENT_USER_QUERY_KEY)) {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, null)
      toast.error('You were signed out. Sign in again.')
    }

    return undefined
  },
})
