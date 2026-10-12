import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']

type PersonaFilterProps = {
  personas: PersonaResponseDto[]
  personaIdentity: string | undefined
  onChange: (personaIdentity: string | undefined) => void
}

const ALL_PERSONAS = 'all'

export function PersonaFilter({ personas, personaIdentity, onChange }: PersonaFilterProps) {
  return (
    <Select
      value={personaIdentity ?? ALL_PERSONAS}
      onValueChange={(value) => onChange(value === ALL_PERSONAS ? undefined : value)}
    >
      <SelectTrigger aria-label="Filter by persona" className="w-full sm:w-64">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_PERSONAS}>All personas</SelectItem>
        {personas.map((persona) => (
          <SelectItem key={persona.identity} value={persona.identity}>
            {persona.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
