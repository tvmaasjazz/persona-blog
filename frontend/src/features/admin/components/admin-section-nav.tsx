import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'

type AdminSectionNavProps = {
  // Whether the user holds INVITE_READ
  canReadInvites: boolean
}

export function AdminSectionNav({ canReadInvites }: AdminSectionNavProps) {
  const sections = [
    { to: '/admin/users', label: 'Users', isShown: true },
    { to: '/admin/invites', label: 'Invites', isShown: canReadInvites },
  ]

  return (
    <nav aria-label="Admin sections" className="flex gap-2">
      {sections
        .filter((section) => section.isShown)
        .map((section) => (
          <NavLink
            key={section.to}
            to={section.to}
            className={({ isActive }) =>
              cn(
                'rounded-xl px-4 py-2 text-[15px] hover:bg-accent',
                isActive && 'bg-accent font-semibold',
              )
            }
          >
            {section.label}
          </NavLink>
        ))}
    </nav>
  )
}
