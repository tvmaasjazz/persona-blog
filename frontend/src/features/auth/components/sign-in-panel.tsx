import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { SignInResultNotice } from '@/features/auth/components/sign-in-result-notice'
import { findSignInResult } from '@/features/auth/sign-in-result-messages'
import { formatUsd } from '@/lib/format-usd'

type SignInPanelProps = {
  searchParams: URLSearchParams
}

// The sign-in page's content: its heading, the redirect's result, and the card when signed out.
export function SignInPanel({ searchParams }: SignInPanelProps) {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div className="flex max-w-sm flex-col gap-4">
        <h1 className="text-xl font-extrabold">Sign in</h1>
        <div className="h-40 rounded-2xl bg-accent" />
      </div>
    )
  }

  // An accepted invite while signed out comes from a stale link, so it counts as no code
  const foundResult = findSignInResult(
    searchParams,
    user ? formatUsd(user.credit_balance_usd) : null,
  )
  const result = foundResult?.kind === 'accepted' && !user ? null : foundResult

  let heading = 'Sign in'
  if (result?.kind === 'accepted') {
    heading = "You're in"
  } else if (user) {
    heading = "You're signed in"
  }

  // Heading, the result or a link home, then the card when signed out
  return (
    <div className="flex max-w-sm flex-col gap-4">
      <h1 className="text-xl font-extrabold">{heading}</h1>
      {result && <SignInResultNotice result={result} isSignedIn={Boolean(user)} />}
      {user && !result && (
        <Button asChild variant="secondary" className="self-start">
          <Link to="/">Go home</Link>
        </Button>
      )}
      {!user && <SignInCard isTitleHidden />}
    </div>
  )
}
