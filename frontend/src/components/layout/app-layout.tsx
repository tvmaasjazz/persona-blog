import { Home, PenSquare, Plus, Sparkles } from 'lucide-react'
import { Link, Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { UserMenu } from '@/features/auth/components/user-menu'

export function AppLayout() {
  const { data: user, isPending } = useCurrentUser()

  return (
    <div className="mx-auto flex min-h-screen max-w-[1200px] justify-center">
      <nav className="flex w-16 shrink-0 flex-col border-r px-2 py-4 md:w-[200px] md:px-3">
        <Sparkles aria-hidden className="mb-4 size-6 self-center text-primary-text md:self-start" />
        <ul className="flex flex-col gap-1">
          <li>
            <Link
              to="/"
              className="flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start"
            >
              <Home aria-hidden className="size-5" />
              <span className="hidden md:inline">Home</span>
            </Link>
          </li>
          <li>
            <span
              title="Writing arrives with the generator"
              className="flex h-12 items-center justify-center gap-3 rounded-xl px-2 text-muted-foreground opacity-50 md:justify-start"
            >
              <PenSquare aria-hidden className="size-5" />
              <span className="hidden md:inline">Write</span>
            </span>
          </li>
        </ul>
        <Button disabled className="mt-3 w-full px-0 md:px-4">
          <Plus aria-hidden className="size-5 md:hidden" />
          <span className="hidden md:inline">Create</span>
        </Button>
        <div className="mt-auto">
          {isPending ? (
            <div className="h-12 rounded-xl bg-accent" />
          ) : (
            user && <UserMenu user={user} />
          )}
        </div>
      </nav>

      <main className="w-full max-w-[600px] px-6 py-8">
        <Outlet />
      </main>

      <aside className="hidden w-[370px] shrink-0 px-6 py-8 lg:block">
        {isPending ? <div className="h-40 rounded-2xl bg-accent" /> : !user && <SignInCard />}
      </aside>
    </div>
  )
}
