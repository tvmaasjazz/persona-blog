import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'

async function deleteBlogPost(blogPostIdentity: string) {
  const { error, response } = await apiClient.DELETE('/blog-posts/{blog_post_identity}', {
    params: { path: { blog_post_identity: blogPostIdentity } },
  })

  if (error) {
    throw createApiError(error, response)
  }
}

export function useDeleteBlogPost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteBlogPost,
    onSuccess: (_result, blogPostIdentity) => {
      queryClient.removeQueries({ queryKey: ['blog-posts', blogPostIdentity] })
      return queryClient.invalidateQueries({ queryKey: ['blog-posts'] })
    },
  })
}
