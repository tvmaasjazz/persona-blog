import { useParams } from 'react-router'

import { QueryErrorState } from '@/components/query-error-state'
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
    return (
      <>
        <h1 className="sr-only">Loading persona</h1>
        <div className="h-40 rounded-2xl bg-accent" aria-hidden />
      </>
    )
  }

  // Not found, or someone else's private persona
  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Persona not found."
        backTo={{ to: '/', label: 'Go home' }}
        heading="Persona"
      />
    )
  }

  // Owner actions need both ownership and the permission
  const canEdit = persona.is_owner && hasPermission(currentUser, 'PERSONA_WRITE')
  const canWritePost = persona.is_owner && hasPermission(currentUser, 'GENERATE_TEXT_RUN_WRITE')
  const canManagePosts = persona.is_owner && hasPermission(currentUser, 'BLOG_POST_WRITE')

  // The owner is told why no posts show, since drafts, scheduled and private posts don't
  let emptyMessage = 'No posts yet.'
  if (persona.is_owner) {
    emptyMessage = persona.is_public
      ? 'No public posts yet.'
      : 'No posts show here while this persona is private.'
  }

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
        emptyMessage={<p className="text-muted-foreground">{emptyMessage}</p>}
      />
    </div>
  )
}
