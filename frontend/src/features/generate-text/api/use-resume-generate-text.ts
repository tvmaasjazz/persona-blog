import { useMutation, useQueryClient } from '@tanstack/react-query'

import { generateTextRunQueryOptions } from '@/features/generate-text/api/generate-text-run-query'
import { apiClient } from '@/lib/api-client'
import { ApiError, createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type ResumeGenerateTextDto = components['schemas']['ResumeGenerateTextDto']

type ResumeGenerateTextVariables = {
  runIdentity: string
  resume: ResumeGenerateTextDto
}

async function resumeGenerateText({ runIdentity, resume }: ResumeGenerateTextVariables) {
  const { data, error, response } = await apiClient.POST(
    '/generate-text/runs/{run_identity}/resume',
    {
      params: { path: { run_identity: runIdentity } },
      body: resume,
    },
  )

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function useResumeGenerateText() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: resumeGenerateText,
    onSuccess: (run) => {
      queryClient.setQueryData(generateTextRunQueryOptions(run.run_identity).queryKey, run)
    },
    // A failed resume marks the run FAILED on the server, so refetch to show it.
    onError: (error, { runIdentity }) => {
      void queryClient.invalidateQueries({
        queryKey: generateTextRunQueryOptions(runIdentity).queryKey,
      })
      // A 402 means the balance has changed since it was shown, so refetch it.
      if (error instanceof ApiError && error.status === 402) {
        void queryClient.invalidateQueries({ queryKey: ['users', 'me'] })
      }
    },
  })
}
