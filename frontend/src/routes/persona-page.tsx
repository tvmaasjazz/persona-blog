import { useParams } from 'react-router'

import { BlogPostList } from '@/features/blog-posts/components/blog-post-list'
import { usePersonaList } from '@/features/personas/api/persona-list-query'
import { PersonaProfile } from '@/features/personas/components/persona-profile'

export function PersonaPage() {
  const { personaIdentity } = useParams()
  const { data: personaList } = usePersonaList()

  if (!personaIdentity) {
    return null
  }

  return (
    <PersonaProfile
      personaIdentity={personaIdentity}
      posts={
        <BlogPostList
          personaIdentity={personaIdentity}
          personas={personaList?.personas ?? []}
          isCompact
          emptyState={<p className="text-muted-foreground">No posts from this persona yet.</p>}
        />
      }
    />
  )
}
