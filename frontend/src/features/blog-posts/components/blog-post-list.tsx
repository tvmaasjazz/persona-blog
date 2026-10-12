import type { ReactNode } from 'react'

import { useBlogPostList } from '@/features/blog-posts/api/blog-post-list-query'
import { BlogPostCard } from '@/features/blog-posts/components/blog-post-card'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type BlogPostListProps = {
  personaIdentity?: string
  personas: PersonaResponseDto[]
  emptyState: ReactNode
}

export function BlogPostList({ personaIdentity, personas, emptyState }: BlogPostListProps) {
  const { data: blogPostList, isPending, isError } = useBlogPostList(personaIdentity)

  if (isPending) {
    return (
      <div className="flex flex-col gap-3">
        <div className="h-24 rounded-2xl bg-accent" />
        <div className="h-24 rounded-2xl bg-accent" />
        <div className="h-24 rounded-2xl bg-accent" />
      </div>
    )
  }

  if (isError) {
    return <p className="text-muted-foreground">Couldn't load your posts. Try again.</p>
  }

  if (blogPostList.blog_posts.length === 0) {
    return emptyState
  }

  return (
    <div className="flex flex-col gap-3">
      {blogPostList.blog_posts.map((blogPost) => (
        <BlogPostCard
          key={blogPost.identity}
          blogPost={blogPost}
          persona={personas.find((persona) => persona.identity === blogPost.persona_identity)}
        />
      ))}
    </div>
  )
}
