import { Link, useParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { SaveRunAsPostForm } from '@/features/blog-posts/components/save-run-as-post-form'
import { useGenerateTextRun } from '@/features/generate-text/api/generate-text-run-query'
import { GenerateTextRunView } from '@/features/generate-text/components/generate-text-run-view'
import { usePersonaList } from '@/features/personas/api/persona-list-query'
import { ApiError, apiErrorMessage } from '@/lib/api-error'

type LoadedRunProps = {
  runIdentity: string
}

function LoadedRun({ runIdentity }: LoadedRunProps) {
  const { data: run, isPending, error } = useGenerateTextRun(runIdentity)
  const { data: personaList } = usePersonaList()

  if (isPending) {
    return <div className="mx-auto h-40 max-w-[720px] rounded-2xl bg-accent" />
  }

  if (error) {
    const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

    return (
      <div className="mx-auto flex max-w-[720px] flex-col items-start gap-4">
        <p className="text-muted-foreground">
          {isNotFound ? 'Run not found' : apiErrorMessage(error)}
        </p>
        <Button asChild variant="secondary">
          <Link to="/write">Back to writing</Link>
        </Button>
      </div>
    )
  }

  const persona = personaList?.personas.find(
    (candidate) => candidate.identity === run.persona_identity,
  )

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
