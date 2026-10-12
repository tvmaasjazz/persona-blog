import { Link, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { BlogPostList } from '@/features/blog-posts/components/blog-post-list'
import { PersonaFilter } from '@/features/blog-posts/components/persona-filter'
import { usePersonaList } from '@/features/personas/api/persona-list-query'

export function BlogPostsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: personaList } = usePersonaList()
  const personaIdentity = searchParams.get('persona') ?? undefined
  const personas = personaList?.personas ?? []

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-extrabold">My Posts</h1>
      <PersonaFilter
        personas={personas}
        personaIdentity={personaIdentity}
        onChange={(nextIdentity) =>
          setSearchParams(nextIdentity ? { persona: nextIdentity } : {}, { replace: true })
        }
      />
      <BlogPostList
        personaIdentity={personaIdentity}
        personas={personas}
        emptyState={
          <div className="flex flex-col items-start gap-4 rounded-2xl border bg-card p-6">
            <p className="text-muted-foreground">No posts yet. Write your first one.</p>
            <Button asChild>
              <Link to="/write">Write a post</Link>
            </Button>
          </div>
        }
      />
    </div>
  )
}
