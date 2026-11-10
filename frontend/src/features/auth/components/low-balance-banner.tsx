import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import { formatUsd } from '@/lib/format-usd'

export function LowBalanceBanner() {
  const { data: user } = useCurrentUser()

  if (!user || !user.is_credit_balance_low || !hasPermission(user, 'GENERATE_TEXT_RUN_WRITE')) {
    return null
  }

  return (
    <p role="status" className="mb-6 rounded-xl border border-destructive p-3 text-sm">
      Your credit balance is low ({formatUsd(user.credit_balance_usd)}). Writing stops when it runs
      out.
    </p>
  )
}
