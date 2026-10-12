import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

type BlogPostDto = components['schemas']['BlogPostDto']

type UpdateBlogPostVariables = {
  blogPostIdentity: string
  blogPost: BlogPostDto
}

async function updateBlogPost({ blogPostIdentity, blogPost }: UpdateBlogPostVariables) {
  const { error, response } = await apiClient.PUT('/blog-posts/{blog_post_identity}', {
    params: { path: { blog_post_identity: blogPostIdentity } },
    body: blogPost,
  })

  if (error) {
    throw createApiError(error, response)
  }
}

export function useUpdateBlogPost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateBlogPost,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blog-posts'] }),
  })
}
