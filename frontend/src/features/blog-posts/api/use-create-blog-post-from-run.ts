import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type CreateBlogPostFromGenerateTextRunDto =
  components['schemas']['CreateBlogPostFromGenerateTextRunDto']

async function createBlogPostFromRun(
  blogPostFromRun: CreateBlogPostFromGenerateTextRunDto,
): Promise<string> {
  const { data, error, response } = await apiClient.POST('/blog-posts/from-generate-text-run', {
    body: blogPostFromRun,
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data.identity
}

export function useCreateBlogPostFromRun() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createBlogPostFromRun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blog-posts'] }),
  })
}
