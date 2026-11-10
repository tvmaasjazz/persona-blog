import type { LucideIcon } from 'lucide-react'
import { Link, matchPath, NavLink, useLocation } from 'react-router'

import { cn } from '@/lib/utils'

type NavItemProps = {
  to: string
  label: string
  icon: LucideIcon
  isExact?: boolean
  // Route patterns that light the item, instead of matching `to` and what is under it
  activePatterns?: string[]
}

function navItemClassName(isActive: boolean) {
  return cn(
    'flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start',
    isActive && 'bg-accent font-semibold',
  )
}

export function NavItem({ to, label, icon: Icon, isExact, activePatterns }: NavItemProps) {
  const { pathname } = useLocation()

  const content = (
    <>
      <Icon aria-hidden className="size-5" />
      <span className="sr-only md:not-sr-only">{label}</span>
    </>
  )

  // NavLink sets aria-current from its own prefix match, so patterns need a plain Link
  if (activePatterns) {
    const isPatternActive = activePatterns.some((pattern) => matchPath(pattern, pathname))
    return (
      <li>
        <Link
          to={to}
          aria-current={isPatternActive ? 'page' : undefined}
          className={navItemClassName(isPatternActive)}
        >
          {content}
        </Link>
      </li>
    )
  }

  return (
    <li>
      <NavLink to={to} end={isExact} className={({ isActive }) => navItemClassName(isActive)}>
        {content}
      </NavLink>
    </li>
  )
}
