import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

type PersonaAvatarProps = {
  name: string
  avatarUrl: string | null
  isLarge?: boolean
}

export function PersonaAvatar({ name, avatarUrl, isLarge = false }: PersonaAvatarProps) {
  return (
    <Avatar size={isLarge ? 'default' : 'lg'} className={isLarge ? 'size-20' : undefined}>
      {avatarUrl && <AvatarImage src={avatarUrl} alt="" />}
      <AvatarFallback className={isLarge ? 'text-2xl' : undefined}>
        {name.charAt(0).toUpperCase()}
      </AvatarFallback>
    </Avatar>
  )
}
