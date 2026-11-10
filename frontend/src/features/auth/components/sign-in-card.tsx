import { Sparkles } from 'lucide-react'

import { GoogleSignInButton } from '@/components/google-sign-in-button'
import { cn } from '@/lib/utils'

type SignInCardProps = {
  // Where the page's own heading already says it, the title is read but not shown
  isTitleHidden?: boolean
}

export function SignInCard({ isTitleHidden }: SignInCardProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-6 text-center">
      <Sparkles aria-hidden className="size-6 text-primary-text" />
      <p className={cn('text-xl font-extrabold', isTitleHidden && 'sr-only')}>Log in or sign up</p>
      <p className="text-sm text-muted-foreground">
        Sign in to start generating personas and their posts.
      </p>
      <GoogleSignInButton />
    </div>
  )
}
