import { FileText, Home, LogIn, Plus, Shield, Sparkles, Users } from 'lucide-react'
import { Link, Outlet, ScrollRestoration, useMatches } from 'react-router'

import { NavItem } from '@/components/layout/nav-item'
import { Button } from '@/components/ui/button'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { LowBalanceBanner } from '@/features/auth/components/low-balance-banner'
import { SignInCard } from '@/features/auth/components/sign-in-card'
import { UserMenu } from '@/features/auth/components/user-menu'
import { hasPermission } from '@/features/auth/permissions'
import { cn } from '@/lib/utils'

// A route's handle: what it needs from the layout
export type AppRouteHandle = {
  // The main area spans the space right of the nav
  hasSidebar?: boolean
  // The right column's sign-in card is hidden where the page is the sign-in
  isSignInCardHidden?: boolean
  // The main column is up to 1100px wide instead of 720px, for a wide table
  isFullWidth?: boolean
}

export function AppLayout() {
  const { data: user, isPending } = useCurrentUser()
  // Whether the current route has its own sidebar
  const matches = useMatches()
  const hasSidebar = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.hasSidebar,
  )
  const isSignInCardHidden = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.isSignInCardHidden,
  )
  const isFullWidth = matches.some(
    (match) => (match.handle as AppRouteHandle | undefined)?.isFullWidth,
  )
  const isSignedOut = !isPending && !user
  const isSignInCardShown = isSignedOut && !isSignInCardHidden
  // Nav items by permission
  const canWritePersonas = hasPermission(user, 'PERSONA_WRITE')
  const canWritePosts = hasPermission(user, 'BLOG_POST_WRITE')
  const canGenerate = hasPermission(user, 'GENERATE_TEXT_RUN_WRITE')
  const canReadUsers = hasPermission(user, 'USER_READ')

  // Nav, then the page and the sign-in card
  return (
    <div className="flex min-h-screen">
      <ScrollRestoration />
      <nav className="sticky top-0 flex h-screen w-16 shrink-0 flex-col border-r px-2 py-4 md:w-[200px] md:px-3">
        <Sparkles aria-hidden className="mb-4 size-6 self-center text-primary-text md:self-start" />
        <ul className="flex flex-col gap-1">
          <NavItem to="/" label="Home" icon={Home} isExact />
          {canWritePersonas && (
            <NavItem
              to="/personas"
              label="My Personas"
              icon={Users}
              activePatterns={['/personas', '/personas/new', '/personas/:id/edit']}
            />
          )}
          {canWritePosts && (
            <NavItem
              to="/posts"
              label="My Posts"
              icon={FileText}
              activePatterns={['/posts', '/posts/:id/edit']}
            />
          )}
          {canReadUsers && <NavItem to="/admin/users" label="Admin" icon={Shield} />}
        </ul>
        {canGenerate && (
          <Button asChild className="mt-3 w-full px-0 md:px-4">
            <Link to="/write">
              <Plus aria-hidden className="size-5 md:hidden" />
              <span className="sr-only md:not-sr-only">Create</span>
            </Link>
          </Button>
        )}
        <div className="mt-auto">
          {isPending ? (
            <div className="h-12 rounded-xl bg-accent" />
          ) : (
            user && <UserMenu user={user} />
          )}
          {isSignedOut && (
            <ul className="lg:hidden">
              <NavItem to="/sign-in" label="Sign in" icon={LogIn} />
            </ul>
          )}
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 justify-center gap-10 px-6 py-8">
        <main
          className={cn(
            'w-full min-w-0',
            !hasSidebar && (isFullWidth ? 'max-w-[1100px]' : 'max-w-[720px]'),
          )}
        >
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
