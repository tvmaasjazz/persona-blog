import { READER_NO_ACCESS_MESSAGE } from '@/features/auth/no-access-message'
import type { components } from '@/lib/api-schema.gen'
import { formatUsd } from '@/lib/format-usd'

type UserResponseDto = components['schemas']['UserResponseDto']

type AccountDetailsProps = {
  user: UserResponseDto
  canGenerate: boolean
}

export function AccountDetails({ user, canGenerate }: AccountDetailsProps) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
        <dt className="text-muted-foreground">Name</dt>
        <dd className="min-w-0 break-words">{user.display_name ?? 'Not set'}</dd>
        <dt className="text-muted-foreground">Email</dt>
        <dd className="break-all">{user.email}</dd>
        <dt className="text-muted-foreground">Role</dt>
        <dd className="capitalize">{user.role.toLowerCase()}</dd>
        {canGenerate && (
          <>
            <dt className="text-muted-foreground">Balance</dt>
            <dd>{formatUsd(user.credit_balance_usd)}</dd>
          </>
        )}
      </dl>
      {!canGenerate && <p className="text-sm text-muted-foreground">{READER_NO_ACCESS_MESSAGE}</p>}
    </section>
  )
}
