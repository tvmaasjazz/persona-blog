import { FileText, Home, Plus, Sparkles, Users } from 'lucide-react'
import { Link, Outlet, ScrollRestoration, useMatches } from 'react-router'

import { NavItem } from '@/components/layout/nav-item'
import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { LowBalanceBanner } from '@/features/auth/components/low-balance-banner'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { UserMenu } from '@/features/auth/components/user-menu'
import { hasPermission } from '@/features/auth/permissions'
import { cn } from '@/lib/utils'

// A route's handle; hasSidebar makes the main area span the space right of the nav.
export type AppRouteHandle = {
  hasSidebar?: boolean
}

export function AppLayout() {
  const { data: user, isPending } = useCurrentUser()
  // Whether the current route has its own sidebar
  const matches = useMatches()
  const hasSidebar = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.hasSidebar,
  )
  const isSignInCardShown = !isPending && !user
  // Nav items by permission
  const canWritePersonas = hasPermission(user, 'PERSONA_WRITE')
  const canWritePosts = hasPermission(user, 'BLOG_POST_WRITE')
  const canGenerate = hasPermission(user, 'GENERATE_TEXT_RUN_WRITE')

  // Nav, then the page and the sign-in card
  return (
    <div className="flex min-h-screen">
      <ScrollRestoration />
      <nav className="sticky top-0 flex h-screen w-16 shrink-0 flex-col border-r px-2 py-4 md:w-[200px] md:px-3">
        <Sparkles aria-hidden className="mb-4 size-6 self-center text-primary-text md:self-start" />
        <ul className="flex flex-col gap-1">
          <NavItem to="/" label="Home" icon={Home} isExact />
          {canWritePersonas && <NavItem to="/personas" label="My Personas" icon={Users} />}
          {canWritePosts && <NavItem to="/posts" label="My Posts" icon={FileText} />}
        </ul>
        {canGenerate && (
          <Button asChild className="mt-3 w-full px-0 md:px-4">
            <Link to="/write">
              <Plus aria-hidden className="size-5 md:hidden" />
              <span className="hidden md:inline">Create</span>
            </Link>
          </Button>
        )}
        <div className="mt-auto">
          {isPending ? (
            <div className="h-12 rounded-xl bg-accent" />
          ) : (
            user && <UserMenu user={user} />
          )}
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 justify-center gap-10 px-6 py-8">
        <main className={cn('w-full min-w-0', !hasSidebar && 'max-w-[720px]')}>
          <LowBalanceBanner />
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
