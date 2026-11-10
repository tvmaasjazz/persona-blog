import type { components } from '@/lib/api-schema.gen'
import { formatDateTime } from '@/lib/format-date'
import { formatUsd } from '@/lib/format-usd'

type AdminUserResponseDto = components['schemas']['AdminUserResponseDto']

type UserAccountCardProps = {
  user: AdminUserResponseDto
}

export function UserAccountCard({ user }: UserAccountCardProps) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-5">
      <h2 className="text-xl font-extrabold">Account</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
        <dt className="text-muted-foreground">Email</dt>
        <dd className="break-all">{user.email}</dd>
        <dt className="text-muted-foreground">Name</dt>
        <dd className="min-w-0 break-words">{user.display_name ?? 'Not set'}</dd>
        <dt className="text-muted-foreground">Role</dt>
        <dd className="capitalize">{user.role.toLowerCase()}</dd>
        <dt className="text-muted-foreground">Balance</dt>
        <dd>{formatUsd(user.credit_balance_usd)}</dd>
        <dt className="text-muted-foreground">Status</dt>
        <dd>{user.is_active ? 'Active' : 'Suspended'}</dd>
        <dt className="text-muted-foreground">Joined</dt>
        <dd>{formatDateTime(user.created_at)}</dd>
        <dt className="text-muted-foreground">Last active</dt>
        <dd>{user.last_activity_at ? formatDateTime(user.last_activity_at) : 'Never'}</dd>
      </dl>
    </section>
  )
}
