import { useParams } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { InviteOffer } from '@/features/invites/components/invite-offer'

export function InvitePage() {
  const { inviteCode } = useParams()
  const { data: user, isPending } = useCurrentUser()

  return (
    <div className="flex max-w-sm flex-col gap-4">
      <h1 className="text-xl font-extrabold">Invite</h1>
      {!inviteCode || isPending ? (
        <div className="h-40 rounded-2xl bg-accent" />
      ) : (
        <InviteOffer inviteCode={inviteCode} isSignedIn={Boolean(user)} />
      )}
    </div>
  )
}
