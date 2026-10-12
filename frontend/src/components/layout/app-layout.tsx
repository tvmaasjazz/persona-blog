import { FileText, Home, Plus, Sparkles, Users } from 'lucide-react'
import { Link, NavLink, Outlet, ScrollRestoration, useMatches } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { UserMenu } from '@/features/auth/components/user-menu'
import { cn } from '@/lib/utils'

// A route's handle. A page that lays out its own right sidebar, like a persona's posts,
// sets hasSidebar so the main column is wide enough for both.
export type AppRouteHandle = {
  hasSidebar?: boolean
}

export function AppLayout() {
  const { data: user, isPending } = useCurrentUser()
  const matches = useMatches()
  const hasSidebar = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.hasSidebar,
  )
  const isSignInCardShown = !isPending && !user

  return (
    <div className="flex min-h-screen">
      <ScrollRestoration />
      <nav className="sticky top-0 flex h-screen w-16 shrink-0 flex-col border-r px-2 py-4 md:w-[200px] md:px-3">
        <Sparkles aria-hidden className="mb-4 size-6 self-center text-primary-text md:self-start" />
        <ul className="flex flex-col gap-1">
          <li>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start',
                  isActive && 'bg-accent font-semibold',
                )
              }
            >
              <Home aria-hidden className="size-5" />
              <span className="hidden md:inline">Home</span>
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/personas"
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start',
                  isActive && 'bg-accent font-semibold',
                )
              }
            >
              <Users aria-hidden className="size-5" />
              <span className="hidden md:inline">My Personas</span>
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/posts"
              className={({ isActive }) =>
                cn(
                  'flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start',
                  isActive && 'bg-accent font-semibold',
                )
              }
            >
              <FileText aria-hidden className="size-5" />
              <span className="hidden md:inline">My Posts</span>
            </NavLink>
          </li>
        </ul>
        <Button asChild className="mt-3 w-full px-0 md:px-4">
          <Link to="/write">
            <Plus aria-hidden className="size-5 md:hidden" />
            <span className="hidden md:inline">Create</span>
          </Link>
        </Button>
        <div className="mt-auto">
          {isPending ? (
            <div className="h-12 rounded-xl bg-accent" />
          ) : (
            user && <UserMenu user={user} />
          )}
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 justify-center gap-10 px-6 py-8">
        <main className={cn('w-full min-w-0', hasSidebar ? 'max-w-[960px]' : 'max-w-[600px]')}>
          <Outlet />
        </main>

        {isSignInCardShown && (
          <aside className="hidden w-[370px] shrink-0 lg:block">
            <SignInCard />
          </aside>
        )}
      </div>
    </div>
  )
}
