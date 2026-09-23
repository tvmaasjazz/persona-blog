import { LogOut } from 'lucide-react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useSignOut } from '@/features/auth/api/use-sign-out'
import type { components } from '@/lib/api-schema.gen'

type UserResponseDto = components['schemas']['UserResponseDto']

type UserMenuProps = {
  user: UserResponseDto
}

export function UserMenu({ user }: UserMenuProps) {
  const signOut = useSignOut()

  const label = user.display_name ?? user.email
  const initial = label.charAt(0).toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-xl p-2 text-left hover:bg-accent">
        <Avatar>
          {user.avatar_url && <AvatarImage src={user.avatar_url} alt="" />}
          <AvatarFallback>{initial}</AvatarFallback>
        </Avatar>
        <span className="hidden truncate text-sm font-semibold md:inline">{label}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuItem disabled={signOut.isPending} onSelect={() => signOut.mutate()}>
          <LogOut aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
