import { ListChecks, Pencil, PenLine } from 'lucide-react'
import { Link } from 'react-router'

import { PersonaAvatar } from '@/components/persona-avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DeletePersonaButton } from '@/features/personas/components/delete-persona-button'
import type { components } from '@/lib/api-schema.gen'

type PublicPersonaResponseDto = components['schemas']['PublicPersonaResponseDto']

type PersonaHeaderProps = {
  persona: PublicPersonaResponseDto
  // The route sets each from the signed-in user's permissions
  canEdit: boolean
  canWritePost: boolean
  canManagePosts: boolean
}

// The persona's avatar, name and bio, and the owner's actions.
export function PersonaHeader({
  persona,
  canEdit,
  canWritePost,
  canManagePosts,
}: PersonaHeaderProps) {
  const hasActions = canEdit || canWritePost || canManagePosts

  return (
    <header className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <PersonaAvatar name={persona.name} avatarUrl={persona.avatar_url} isLarge />
        <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
          <h1 className="text-xl font-extrabold wrap-anywhere">{persona.name}</h1>
          {persona.is_owner && !persona.is_public && <Badge variant="outline">Private</Badge>}
        </div>
      </div>
      <p className="whitespace-pre-wrap">{persona.bio}</p>
      {persona.is_owner && !persona.is_public && (
        <p className="text-muted-foreground">
          This persona is private. Readers can't see it or its posts.
        </p>
      )}
      {hasActions && (
        <div className="flex flex-wrap items-center gap-2">
          {canEdit && (
            <Button asChild variant="secondary">
              <Link to={`/personas/${persona.identity}/edit`}>
                <Pencil aria-hidden />
                Edit
              </Link>
            </Button>
          )}
          {canWritePost && (
            <Button asChild>
              <Link to={`/write?persona=${persona.identity}`}>
                <PenLine aria-hidden />
                Write a post
              </Link>
            </Button>
          )}
          {canManagePosts && (
            <Button asChild variant="secondary">
              <Link to={`/posts?persona=${persona.identity}`}>
                <ListChecks aria-hidden />
                Manage posts
              </Link>
            </Button>
          )}
          {canEdit && (
            <DeletePersonaButton personaIdentity={persona.identity} personaName={persona.name} />
          )}
        </div>
      )}
    </header>
  )
}
