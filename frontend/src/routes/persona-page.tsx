import { ListChecks } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import { PublicBlogPostFeed } from '@/features/blog-posts/components/public-blog-post-feed'
import { usePublicPersona } from '@/features/personas/api/public-persona-query'
import { PersonaHeader } from '@/features/personas/components/persona-header'
import { PersonaVoiceDetails } from '@/features/personas/components/persona-voice-details'

export function PersonaPage() {
  const { personaIdentity } = useParams()

  if (!personaIdentity) {
    return null
  }

  return <LoadedPersonaPage personaIdentity={personaIdentity} />
}

type LoadedPersonaPageProps = {
  personaIdentity: string
}

// Split out so the hooks run only with an identity.
function LoadedPersonaPage({ personaIdentity }: LoadedPersonaPageProps) {
  const { data: persona, isPending, error } = usePublicPersona(personaIdentity)
  const { data: currentUser } = useCurrentUser()

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" aria-hidden />
  }

  // Not found, or someone else's private persona
  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Persona not found."
        backTo={{ to: '/', label: 'Go home' }}
      />
    )
  }

  // Owner actions need both ownership and the permission
  const canEdit = persona.is_owner && hasPermission(currentUser, 'PERSONA_WRITE')
  const canWritePost = persona.is_owner && hasPermission(currentUser, 'GENERATE_TEXT_RUN_WRITE')
  const canManagePosts = persona.is_owner && hasPermission(currentUser, 'BLOG_POST_WRITE')

  // A private persona's posts are hidden from readers, so the owner is told why none show
  const emptyMessage =
    persona.is_owner && !persona.is_public ? (
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-muted-foreground">Readers see no posts while this persona is private.</p>
        {canManagePosts && (
          <Button asChild variant="secondary">
            <Link to={`/posts?persona=${persona.identity}`}>
              <ListChecks aria-hidden />
              Manage posts
            </Link>
          </Button>
        )}
      </div>
    ) : (
      <p className="text-muted-foreground">No posts yet.</p>
    )

  // Header, the owner's voice details, then the posts
  return (
    <div className="flex flex-col gap-8">
      <PersonaHeader
        persona={persona}
        canEdit={canEdit}
        canWritePost={canWritePost}
        canManagePosts={canManagePosts}
      />
      {persona.is_owner && <PersonaVoiceDetails personaIdentity={persona.identity} />}
      <PublicBlogPostFeed
        params={{
          persona_identity: persona.identity,
          sort_by: 'PUBLISHED_AT',
          sort_direction: 'DESC',
        }}
        emptyMessage={emptyMessage}
      />
    </div>
  )
}
