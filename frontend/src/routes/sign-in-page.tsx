import { Link, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { SignInResultNotice } from '@/features/auth/components/sign-in-result-notice'
import { findSignInResult } from '@/features/auth/sign-in-result-messages'
import { formatUsd } from '@/lib/format-usd'

export function SignInPage() {
  const { data: user, isPending } = useCurrentUser()
  const [searchParams] = useSearchParams()

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  const balanceText = user ? formatUsd(user.credit_balance_usd) : null
  const result = findSignInResult(searchParams, balanceText)

  // A redirect's code, with the card under it when signed out
  if (result) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-xl font-extrabold">Sign in</h1>
        <SignInResultNotice result={result} isSignedIn={Boolean(user)} />
        {!user && <SignInCard />}
      </div>
    )
  }

  // No code: the card, or a link home
  if (user) {
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-xl font-extrabold">You're signed in</h1>
        <Button asChild variant="secondary">
          <Link to="/">Go home</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-extrabold">Sign in</h1>
      <SignInCard />
    </div>
  )
}
