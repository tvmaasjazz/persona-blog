import { Navigate, Outlet } from 'react-router'

import { useCurrentUser } from '@/features/auth/api/current-user-query'

export function RequireAuth() {
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

  return <Outlet />
}
