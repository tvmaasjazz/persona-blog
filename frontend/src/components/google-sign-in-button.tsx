import { Button } from '@/components/ui/button'

type GoogleSignInButtonProps = {
  inviteCode?: string
}

export function GoogleSignInButton({ inviteCode }: GoogleSignInButtonProps) {
  const href =
    inviteCode === undefined
      ? '/api/auth/google/login'
      : `/api/auth/google/login?invite_code=${encodeURIComponent(inviteCode)}`

  return (
    <Button asChild className="w-full">
      <a href={href}>Continue with Google</a>
    </Button>
  )
}
