import { useMutation, useQueryClient } from '@tanstack/react-query'

import { generateTextRunQueryOptions } from '@/features/generate-text/api/generate-text-run-query'
import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type GenerateBlogPostDto = components['schemas']['GenerateBlogPostDto']

async function generateBlogPost(generateBlogPostBody: GenerateBlogPostDto) {
  const { data, error, response } = await apiClient.POST('/generate-text/blog-post', {
    body: generateBlogPostBody,
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}

export function useGenerateBlogPost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: generateBlogPost,
    onSuccess: (run) => {
      queryClient.setQueryData(generateTextRunQueryOptions(run.run_identity).queryKey, run)
    },
  })
}
