import { useSearchParams } from 'react-router'

import { SignInPanel } from '@/features/auth/components/sign-in-panel'

export function SignInPage() {
  const [searchParams] = useSearchParams()

  return <SignInPanel searchParams={searchParams} />
}
