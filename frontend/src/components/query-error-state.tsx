import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { ApiError, apiErrorMessage } from '@/lib/api-error'

type QueryErrorStateProps = {
  error: Error
  // Given, a 404 or 422 reads as not found
  notFoundMessage?: string
  backTo?: { to: string; label: string }
  // Given when the error replaces the whole page, as its h1
  heading?: string
}

export function QueryErrorState({ error, notFoundMessage, backTo, heading }: QueryErrorStateProps) {
  // A bad identity is a 422, which reads the same as a missing one
  const isNotFound =
    notFoundMessage !== undefined &&
    error instanceof ApiError &&
    (error.status === 404 || error.status === 422)
  const hasApiMessage = error instanceof ApiError && typeof error.detail === 'string'

  let message = 'Something went wrong. Try again, or reload the page.'
  if (isNotFound) {
    message = `${notFoundMessage} It may have been deleted, or the link is wrong.`
  } else if (hasApiMessage) {
    message = `${apiErrorMessage(error)} Try again, or reload the page.`
  }

  return (
    <div className="mx-auto flex max-w-[720px] flex-col items-start gap-4">
      {heading && <h1 className="text-xl font-extrabold">{heading}</h1>}
      <p className="text-muted-foreground">{message}</p>
      {backTo && (
        <Button asChild variant="secondary">
          <Link to={backTo.to}>{backTo.label}</Link>
        </Button>
      )}
    </div>
  )
}
