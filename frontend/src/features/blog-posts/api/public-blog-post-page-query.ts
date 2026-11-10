import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { paths } from '@/lib/api-schema.gen'

export type PublicBlogPostPageQuery = NonNullable<
  paths['/blog-posts/public']['get']['parameters']['query']
>

export async function findPublicBlogPostPage(params: PublicBlogPostPageQuery) {
  const { data, error, response } = await apiClient.GET('/blog-posts/public', {
    params: { query: params },
  })

  if (error) {
    throw createApiError(error, response)
  }

  return data
}
