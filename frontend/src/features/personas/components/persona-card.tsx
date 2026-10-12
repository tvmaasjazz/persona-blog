import { Link } from 'react-router'

import { PersonaAvatar } from '@/components/persona-avatar'
import { Badge } from '@/components/ui/badge'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type PersonaCardProps = {
  persona: PersonaResponseDto
}

export function PersonaCard({ persona }: PersonaCardProps) {
  return (
    <Link
      to={`/personas/${persona.identity}`}
      className="flex items-start gap-4 rounded-2xl border bg-card p-4 hover:bg-accent"
    >
      <PersonaAvatar name={persona.name} avatarUrl={persona.avatar_url} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-bold">{persona.name}</span>
        <p className="line-clamp-2 text-sm text-muted-foreground">{persona.bio}</p>
      </div>
      <Badge variant={persona.is_public ? 'secondary' : 'outline'}>
        {persona.is_public ? 'Public' : 'Private'}
      </Badge>
    </Link>
  )
}
