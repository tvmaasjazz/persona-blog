import { useParams } from 'react-router'

import { QueryErrorState } from '@/components/query-error-state'
import { SaveRunAsPostForm } from '@/features/blog-posts/components/save-run-as-post-form'
import { useGenerateTextRun } from '@/features/generate-text/api/generate-text-run-query'
import { GenerateTextRunView } from '@/features/generate-text/components/generate-text-run-view'
import { usePersonaOptions } from '@/features/personas/api/user-persona-page-query'

type LoadedRunProps = {
  runIdentity: string
}

function LoadedRun({ runIdentity }: LoadedRunProps) {
  // Load the run and personas
  const { data: run, isPending, error } = useGenerateTextRun(runIdentity)
  const { data: personas } = usePersonaOptions()

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

  // Run view with the save form from blog-posts
  const persona = personas?.find((candidate) => candidate.identity === run.persona_identity)

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
