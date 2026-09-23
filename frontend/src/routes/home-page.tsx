import { useCurrentUser } from '@/features/auth/api/current-user-query'

export function HomePage() {
  const { data: user } = useCurrentUser()

  if (user) {
    const label = user.display_name ?? user.email

    return (
      <div>
        <h1 className="text-xl font-extrabold">Welcome, {label}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          No posts yet. Writing arrives with the generator.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-xl font-extrabold">Welcome</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Sign in with the card on the right to get started.
      </p>
    </div>
  )
}
