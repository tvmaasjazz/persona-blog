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

type RunWithSaveFormProps = {
  run: GenerateTextRunResponseDto
  persona: PersonaResponseDto | undefined
}

type RunPersonaLoaderProps = {
  run: GenerateTextRunResponseDto
  personaIdentity: string
}

function LoadedRun({ runIdentity }: LoadedRunProps) {
  // Load the run
  const { data: run, isPending, error } = useGenerateTextRun(runIdentity)

  if (isPending) {
    return (
      <>
        <h1 className="sr-only">Loading run</h1>
        <div className="mx-auto h-40 max-w-[720px] rounded-2xl bg-accent" aria-hidden />
      </>
    )
  }

  if (error) {
    return (
      <QueryErrorState
        error={error}
        notFoundMessage="Run not found."
        heading="Writing a post"
        backTo={{ to: '/write', label: 'Back to writing' }}
      />
    )
  }

  // A run whose persona was deleted has none to load
  return run.persona_identity ? (
    <RunPersonaLoader run={run} personaIdentity={run.persona_identity} />
  ) : (
    <RunWithSaveForm run={run} persona={undefined} />
  )
}

function RunPersonaLoader({ run, personaIdentity }: RunPersonaLoaderProps) {
  const { data: persona, isPending, error } = usePersona(personaIdentity)

  return (
    <GenerateTextRunView
      run={run}
      personaName={persona?.name ?? null}
      renderCompletedActions={({ onSaved, discardButton }) => {
        // The save form needs the persona's visibility, so wait for it
        if (isPending) {
          return <div className="h-40 rounded-2xl bg-accent" />
        }
        if (error) {
          return <QueryErrorState error={error} />
        }
        return (
          <SaveRunAsPostForm
            runIdentity={run.run_identity}
            isPersonaPublic={persona.is_public}
            onSaved={onSaved}
            secondaryAction={discardButton}
          />
        )
      }}
    />
  )
}

// A run whose persona was deleted: no persona to read, so its posts can't be public
function RunWithSaveForm({ run, persona }: RunWithSaveFormProps) {
  return (
    <GenerateTextRunView
      run={run}
      personaName={persona?.name ?? null}
      renderCompletedActions={({ onSaved, discardButton }) => (
        <SaveRunAsPostForm
          runIdentity={run.run_identity}
          isPersonaPublic={false}
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
