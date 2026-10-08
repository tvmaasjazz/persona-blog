import { FileText, Home, Plus, Sparkles, Users } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { UserMenu } from '@/features/auth/components/user-menu'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const { data: user, isPending } = useCurrentUser()

  return (
    <div className="mx-auto flex min-h-screen max-w-[1200px] justify-center">
      <nav className="flex w-16 shrink-0 flex-col border-r px-2 py-4 md:w-[200px] md:px-3">
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

      <main className="w-full max-w-[600px] px-6 py-8">
        <Outlet />
      </main>

      <aside className="hidden w-[370px] shrink-0 px-6 py-8 lg:block">
        {isPending ? <div className="h-40 rounded-2xl bg-accent" /> : !user && <SignInCard />}
      </aside>
    </div>
  )
}
