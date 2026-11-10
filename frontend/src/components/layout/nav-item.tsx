import type { LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'

type NavItemProps = {
  to: string
  label: string
  icon: LucideIcon
  isExact?: boolean
}

export function NavItem({ to, label, icon: Icon, isExact }: NavItemProps) {
  return (
    <li>
      <NavLink
        to={to}
        end={isExact}
        className={({ isActive }) =>
          cn(
            'flex h-12 items-center justify-center gap-3 rounded-xl px-2 hover:bg-accent md:justify-start',
            isActive && 'bg-accent font-semibold',
          )
        }
      >
        <Icon aria-hidden className="size-5" />
        <span className="sr-only md:not-sr-only">{label}</span>
      </NavLink>
    </li>
  )
}
