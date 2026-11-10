import { GoogleSignInButton } from '@/components/google-sign-in-button'
import { useInviteStatus } from '@/features/invites/api/invite-status-query'
import { ApiError } from '@/lib/api-error'
import { formatUsd } from '@/lib/format-usd'

const UNUSABLE_MESSAGES = {
  USED: 'This invite has already been used.',
  EXPIRED: 'This invite has expired. Ask for a new one.',
  REVOKED: 'This invite is no longer valid. Ask for a new one.',
}

type InviteOfferProps = {
  inviteCode: string
  isSignedIn: boolean
}

export function InviteOffer({ inviteCode, isSignedIn }: InviteOfferProps) {
  const { data: inviteStatus, error, isPending } = useInviteStatus(inviteCode)

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (error) {
    const isUnknownCode = error instanceof ApiError && error.status === 404
    return (
      <p className="text-muted-foreground">
        {isUnknownCode
          ? "This invite link isn't valid."
          : 'Something went wrong checking this invite. Try again, or reload the page.'}
      </p>
    )
  }

  if (inviteStatus.status !== 'UNUSED') {
    return <p className="text-muted-foreground">{UNUSABLE_MESSAGES[inviteStatus.status]}</p>
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border bg-card p-6">
      <h1 className="text-xl font-extrabold">You're invited</h1>
      <p>
        This invite gives you {formatUsd(inviteStatus.credit_amount_usd)} in credit to create
        personas and write posts.
      </p>
      {isSignedIn && (
        <p className="text-sm text-muted-foreground">It's added to the account you sign in with.</p>
      )}
      <GoogleSignInButton inviteCode={inviteCode} />
    </div>
  )
}
