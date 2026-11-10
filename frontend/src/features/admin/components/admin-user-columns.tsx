import { Link } from 'react-router'

import type { DataTableColumn } from '@/components/data-table'
import { Badge } from '@/components/ui/badge'
import type { components } from '@/lib/api-schema.gen'
import { formatDate } from '@/lib/format-date'
import { formatUsd } from '@/lib/format-usd'

type AdminUser = components['schemas']['AdminUserResponseDto']
type AdminUserSort = components['schemas']['AdminUserSortType']

function formatRole(role: AdminUser['role']): string {
  return role.charAt(0) + role.slice(1).toLowerCase()
}

export const ADMIN_USER_COLUMNS: DataTableColumn<AdminUser, AdminUserSort>[] = [
  {
    header: 'Email',
    sortValue: 'EMAIL',
    firstSortDirection: 'ASC',
    className: 'min-w-56',
    cell: (user) => (
      <Link to={`/admin/users/${user.identity}`} className="text-primary-text hover:underline">
        {user.email}
      </Link>
    ),
  },
  {
    header: 'Name',
    className: 'min-w-36',
    cell: (user) => user.display_name ?? <span className="text-muted-foreground">No name</span>,
  },
  { header: 'Role', cell: (user) => formatRole(user.role) },
  {
    header: 'Balance',
    className: 'text-right',
    cell: (user) => formatUsd(user.credit_balance_usd),
  },
  {
    header: 'Status',
    cell: (user) =>
      user.is_active ? <span>Active</span> : <Badge variant="destructive">Suspended</Badge>,
  },
  {
    header: 'Joined',
    sortValue: 'CREATED_AT',
    cell: (user) => formatDate(user.created_at),
  },
  {
    header: 'Last active',
    sortValue: 'LAST_ACTIVITY_AT',
    cell: (user) =>
      user.last_activity_at ? (
        formatDate(user.last_activity_at)
      ) : (
        <span className="text-muted-foreground">Never</span>
      ),
  },
]
