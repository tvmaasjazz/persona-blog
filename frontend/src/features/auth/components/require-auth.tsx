import { Navigate, Outlet } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'

export function RequireAuth() {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return <div className="h-40 rounded-2xl bg-accent" />
  }

  if (!user) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
