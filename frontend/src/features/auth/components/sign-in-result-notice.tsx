import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import type { SignInResult } from '@/features/auth/sign-in-result-messages'

type SignInResultNoticeProps = {
  result: SignInResult
  isSignedIn: boolean
}

export function SignInResultNotice({ result, isSignedIn }: SignInResultNoticeProps) {
  // An invite error after Google sign-in still signed the user in
  const isInviteErrorSignedIn = result.kind === 'invite-error' && isSignedIn

  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border bg-card p-6">
      <p role={result.kind === 'accepted' ? 'status' : 'alert'}>{result.message}</p>
      {isInviteErrorSignedIn && (
        <p className="text-sm text-muted-foreground">You're signed in, without the invite.</p>
      )}
      {isSignedIn && (
        <Button asChild variant="secondary">
          <Link to="/">Go home</Link>
        </Button>
      )}
    </div>
  )
}
