import { GoogleSignInButton } from '@/components/google-sign-in-button'
import { QueryErrorState } from '@/components/query-error-state'
import { useInviteStatus } from '@/features/invites/api/invite-status-query'
import { formatUsd } from '@/lib/format-usd'
import { INVITE_MESSAGES } from '@/lib/invite-messages'

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
    return <QueryErrorState error={error} notFoundMessage={INVITE_MESSAGES.NOT_FOUND} />
  }

  if (inviteStatus.status !== 'UNUSED') {
    return <p className="text-muted-foreground">{INVITE_MESSAGES[inviteStatus.status]}</p>
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border bg-card p-6">
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
