import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'

import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { usePersona } from '@/features/personas/api/persona-query'

type PersonaVoiceDetailsProps = {
  personaIdentity: string
}

type VoiceFieldProps = {
  label: string
  value: string | null
  className?: string
}

function VoiceField({ label, value, className }: VoiceFieldProps): ReactNode {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm font-semibold">{label}</dt>
      {value ? (
        <dd className={className ?? 'whitespace-pre-wrap'}>{value}</dd>
      ) : (
        <dd className="text-muted-foreground">Not set</dd>
      )}
    </div>
  )
}

type VoiceDetailsContentProps = {
  personaIdentity: string
}

// Loads the owner's route; it mounts only once the section is opened.
function VoiceDetailsContent({ personaIdentity }: VoiceDetailsContentProps) {
  const { data: persona, isPending, error } = usePersona(personaIdentity)

  if (isPending) {
    return <div className="h-24 rounded-xl bg-accent" />
  }

  if (error) {
    return <QueryErrorState error={error} />
  }

  return (
    <dl className="flex flex-col gap-4">
      <VoiceField label="Background" value={persona.background} />
      <VoiceField label="Writing style" value={persona.writing_style} />
      <VoiceField
        label="Sample writing"
        value={persona.sample_writing}
        className="font-serif whitespace-pre-wrap"
      />
      <VoiceField label="Default tone" value={persona.default_tone} />
      <VoiceField label="Default target audience" value={persona.default_target_audience} />
    </dl>
  )
}

// The owner's voice and defaults, folded away until opened.
export function PersonaVoiceDetails({ personaIdentity }: PersonaVoiceDetailsProps) {
  return (
    <Collapsible className="flex flex-col gap-3 rounded-2xl border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 className="font-bold">Voice and defaults</h2>
        <p className="text-sm text-muted-foreground">Only you can see this</p>
      </div>
      <CollapsibleTrigger asChild>
        <Button variant="link" className="group h-auto self-start px-0">
          <span className="group-data-[state=open]:hidden">Show details</span>
          <span className="hidden group-data-[state=open]:inline">Hide details</span>
          <ChevronDown
            aria-hidden
            className="transition-transform group-data-[state=open]:rotate-180"
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t pt-3">
        <VoiceDetailsContent personaIdentity={personaIdentity} />
      </CollapsibleContent>
    </Collapsible>
  )
}
