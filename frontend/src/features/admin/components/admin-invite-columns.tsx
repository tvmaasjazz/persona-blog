import type { DataTableColumn } from '@/components/data-table'
import { RevokeInviteButton } from '@/features/admin/components/revoke-invite-button'
import type { components } from '@/lib/api-schema.gen'
import { formatDate } from '@/lib/format-date'
import { formatUsd } from '@/lib/format-usd'

type AdminInvite = components['schemas']['AdminInviteResponseDto']
type AdminInviteSort = components['schemas']['AdminInviteSortType']
type InviteStatus = components['schemas']['InviteStatusType']

const STATUS_LABELS: Record<InviteStatus, string> = {
  UNUSED: 'Unused',
  USED: 'Used',
  EXPIRED: 'Expired',
  REVOKED: 'Revoked',
}

// The columns, with a Revoke column only for an admin who can write invites.
export function buildAdminInviteColumns(
  canRevoke: boolean,
): DataTableColumn<AdminInvite, AdminInviteSort>[] {
  const columns: DataTableColumn<AdminInvite, AdminInviteSort>[] = [
    {
      header: 'Name',
      sortValue: 'NAME',
      firstSortDirection: 'ASC',
      className: 'min-w-40',
      cell: (invite) => invite.name,
    },
    {
      header: 'Amount',
      className: 'text-right',
      cell: (invite) => formatUsd(invite.credit_amount_usd),
    },
    { header: 'Status', cell: (invite) => STATUS_LABELS[invite.status] },
    { header: 'Expires', sortValue: 'EXPIRES_AT', cell: (invite) => formatDate(invite.expires_at) },
    {
      header: 'Used by',
      className: 'min-w-48',
      cell: (invite) =>
        invite.used_by_email ?? <span className="text-muted-foreground">Not used</span>,
    },
    { header: 'Made by', className: 'min-w-48', cell: (invite) => invite.created_by_email },
    { header: 'Created', sortValue: 'CREATED_AT', cell: (invite) => formatDate(invite.created_at) },
  ]

  if (canRevoke) {
    columns.push({
      header: 'Actions',
      cell: (invite) =>
        invite.status === 'UNUSED' ? (
          <RevokeInviteButton inviteIdentity={invite.identity} inviteName={invite.name} />
        ) : null,
    })
  }

  return columns
}
