import { Pencil } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePersona } from '@/features/personas/api/persona-query'
import { DeletePersonaButton } from '@/features/personas/components/delete-persona-button'
import { PersonaAvatar } from '@/features/personas/components/persona-avatar'
import { ApiError, apiErrorMessage } from '@/lib/api-error'

type PersonaProfileProps = {
  personaIdentity: string
}

type ProfileFieldProps = {
  label: string
  value: string | null
  className?: string
}

function ProfileField({ label, value, className }: ProfileFieldProps): ReactNode {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold">{label}</h3>
      {value ? (
        <p className={className ?? 'whitespace-pre-wrap'}>{value}</p>
      ) : (
        <p className="text-muted-foreground">Not set</p>
      )}
    </div>
  )
}

export function PersonaProfile({ personaIdentity }: PersonaProfileProps) {
  const { data: persona, isPending, error } = usePersona(personaIdentity)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-muted-foreground">
          {isNotFound ? 'Persona not found' : apiErrorMessage(error)}
        </p>
        <Button asChild variant="secondary">
          <Link to="/personas">Back to personas</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <PersonaAvatar name={persona.name} avatarUrl={persona.avatar_url} isLarge />
          <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
            <h1 className="text-xl font-extrabold break-words">{persona.name}</h1>
            <Badge variant={persona.is_public ? 'secondary' : 'outline'}>
              {persona.is_public ? 'Public' : 'Private'}
            </Badge>
          </div>
        </div>
        <p className="whitespace-pre-wrap">{persona.bio}</p>
        <div className="flex items-center gap-2">
          <Button asChild variant="secondary">
            <Link to={`/personas/${persona.identity}/edit`}>
              <Pencil aria-hidden />
              Edit
            </Link>
          </Button>
          <DeletePersonaButton personaIdentity={persona.identity} personaName={persona.name} />
        </div>
      </header>

      <section className="flex flex-col gap-5">
        <h2 className="text-lg font-bold">Voice</h2>
        <ProfileField label="Background" value={persona.background} />
        <ProfileField label="Expertise" value={persona.expertise} />
        <ProfileField label="Writing style" value={persona.writing_style} />
        <ProfileField
          label="Sample writing"
          value={persona.sample_writing}
          className="font-serif whitespace-pre-wrap"
        />
      </section>

      <section className="flex flex-col gap-5">
        <h2 className="text-lg font-bold">Defaults</h2>
        <ProfileField label="Default tone" value={persona.default_tone} />
        <ProfileField label="Default target audience" value={persona.default_target_audience} />
      </section>
    </div>
  )
}
