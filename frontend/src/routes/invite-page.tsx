import { useParams } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { InviteOffer } from '@/features/invites/components/invite-offer'

export function InvitePage() {
  const { inviteCode } = useParams()
  const { data: user, isPending } = useCurrentUser()

  if (!inviteCode || isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  return <InviteOffer inviteCode={inviteCode} isSignedIn={Boolean(user)} />
}
