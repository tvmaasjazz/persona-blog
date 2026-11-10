import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { ApiError, apiErrorMessage } from '@/lib/api-error'

type QueryErrorStateProps = {
  error: Error
  notFoundMessage: string
  backTo?: { to: string; label: string }
}

export function QueryErrorState({ error, notFoundMessage, backTo }: QueryErrorStateProps) {
  // A bad identity is a 422, which reads the same as a missing one
  const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

  return (
    <div className="mx-auto flex max-w-[720px] flex-col items-start gap-4">
      <p className="text-muted-foreground">
        {isNotFound
          ? `${notFoundMessage} It may have been deleted, or the link is wrong.`
          : `${apiErrorMessage(error)} Try again, or reload the page.`}
      </p>
      {backTo && (
        <Button asChild variant="secondary">
          <Link to={backTo.to}>{backTo.label}</Link>
        </Button>
      )}
    </div>
  )
}
