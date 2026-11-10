import { useParams } from 'react-router'

import { QueryErrorState } from '@/components/query-error-state'
import { SaveRunAsPostForm } from '@/features/blog-posts/components/save-run-as-post-form'
import { useGenerateTextRun } from '@/features/generate-text/api/generate-text-run-query'
import { GenerateTextRunView } from '@/features/generate-text/components/generate-text-run-view'
import { usePersona } from '@/features/personas/api/persona-query'
import type { components } from '@/lib/api-schema.gen'

type PersonaResponseDto = components['schemas']['PersonaResponseDto']
type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

type LoadedRunProps = {
  runIdentity: string
}

type RunViewWithPersonaProps = {
  run: GenerateTextRunResponseDto
  persona: PersonaResponseDto | undefined
}

type RunWithPersonaProps = {
  run: GenerateTextRunResponseDto
  personaIdentity: string
}

function LoadedRun({ runIdentity }: LoadedRunProps) {
  // Load the run
  const { data: run, isPending, error } = useGenerateTextRun(runIdentity)

  if (isPending) {
    return <div className="mx-auto h-40 max-w-[720px] rounded-2xl bg-accent" />
  }

  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Run not found."
        backTo={{ to: '/write', label: 'Back to writing' }}
      />
    )
  }

  // A run whose persona was deleted has none to load
  return run.persona_identity ? (
    <RunWithPersona run={run} personaIdentity={run.persona_identity} />
  ) : (
    <RunViewWithPersona run={run} persona={undefined} />
  )
}

function RunWithPersona({ run, personaIdentity }: RunWithPersonaProps) {
  const { data: persona } = usePersona(personaIdentity)

  return <RunViewWithPersona run={run} persona={persona} />
}

function RunViewWithPersona({ run, persona }: RunViewWithPersonaProps) {
  // Run view with the save form from blog-posts
  return (
    <GenerateTextRunView
      run={run}
      personaName={persona?.name ?? null}
      renderCompletedActions={({ onSaved, discardButton }) => (
        <SaveRunAsPostForm
          runIdentity={run.run_identity}
          isPersonaPublic={persona?.is_public ?? false}
          onSaved={onSaved}
          secondaryAction={discardButton}
        />
      )}
    />
  )
}

export function GenerateTextRunPage() {
  const { runIdentity } = useParams()

  if (!runIdentity) {
    return null
  }

  return <LoadedRun runIdentity={runIdentity} />
}
