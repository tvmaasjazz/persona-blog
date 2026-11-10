import { Navigate, Outlet } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'

type PermissionType = components['schemas']['PermissionType']

type RequirePermissionProps = {
  permission: PermissionType
}

export function RequirePermission({ permission }: RequirePermissionProps) {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (!user) {
    return <Navigate to="/" replace />
  }

  if (!hasPermission(user, permission)) {
    return (
      <p className="text-muted-foreground">
        Your account can read posts. Creating personas and posts is by invitation for now.
      </p>
    )
  }

  return <Outlet />
}
