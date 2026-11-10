import { Navigate, Outlet } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { READER_NO_ACCESS_MESSAGE } from '@/features/auth/no-access-message'
import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'

type PermissionType = components['schemas']['PermissionType']

type RequirePermissionProps = {
  permission: PermissionType
  // Shown when the signed-in user lacks the permission
  message?: string
}

export function RequirePermission({
  permission,
  message = READER_NO_ACCESS_MESSAGE,
}: RequirePermissionProps) {
  const { data: user, isPending } = useCurrentUser()

  // The child page's title isn't known yet
  if (isPending) {
    return (
      <>
        <h1 className="sr-only">Loading</h1>
        <div className="h-40 rounded-2xl bg-accent" aria-hidden />
      </>
    )
  }

  if (!user) {
    return <Navigate to="/sign-in" replace />
  }

  if (!hasPermission(user, permission)) {
    return (
      <div className="mx-auto flex max-w-[720px] flex-col gap-2">
        <h1 className="text-xl font-extrabold">No access</h1>
        <p className="text-muted-foreground">{message}</p>
      </div>
    )
  }

  return <Outlet />
}
