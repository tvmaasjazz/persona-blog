import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { AccountDetails } from '@/features/auth/components/account-details'
import { hasPermission } from '@/features/auth/permissions'

export function AccountPage() {
  const { data: user } = useCurrentUser()

  // The route is behind RequireAuth, so a user is there once it renders
  if (!user) {
    return null
  }

  return (
    <>
      <h1 className="mb-6 text-xl font-extrabold">Account</h1>
      <AccountDetails user={user} canGenerate={hasPermission(user, 'GENERATE_TEXT_RUN_WRITE')} />
    </>
  )
}
