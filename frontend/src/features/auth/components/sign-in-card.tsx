import { Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'

export function SignInCard() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-6 text-center">
      <Sparkles aria-hidden className="size-6 text-primary-text" />
      <p className="text-xl font-extrabold">Log in or sign up</p>
      <p className="text-sm text-muted-foreground">
        Sign in to start generating personas and their posts.
      </p>
      <Button asChild className="w-full">
        <a href="/api/auth/google/login">Continue with Google</a>
      </Button>
    </div>
  )
}
