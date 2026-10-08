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
    <div className="flex flex-col gap-8">
      <PersonaProfile personaIdentity={personaIdentity} />
      <section className="flex flex-col gap-5">
        <h2 className="text-lg font-bold">Posts</h2>
        <BlogPostList
          personaIdentity={personaIdentity}
          personas={personaList?.personas ?? []}
          emptyState={<p className="text-muted-foreground">No posts from this persona yet.</p>}
        />
      </section>
    </div>
  )
}
