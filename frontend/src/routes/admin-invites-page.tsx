import { DataTable } from '@/components/data-table'
import { ListPager } from '@/components/list-pager'
import { ListSearchBox } from '@/components/list-search-box'
import { useAdminInvitePage } from '@/features/admin/api/admin-invite-page-query'
import { buildAdminInviteColumns } from '@/features/admin/components/admin-invite-columns'
import { AdminSectionNav } from '@/features/admin/components/admin-section-nav'
import { CreateInviteForm } from '@/features/admin/components/create-invite-form'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'
import { useListSearchParams } from '@/lib/use-list-search-params'

const PAGE_SIZE = 20
const SORT_VALUES = [
  'CREATED_AT',
  'NAME',
  'EXPIRES_AT',
] as const satisfies readonly components['schemas']['AdminInviteSortType'][]

export function AdminInvitesPage() {
  const { data: currentUser } = useCurrentUser()
  const canCreateInvites = hasPermission(currentUser, 'INVITE_WRITE')
  // Page, search and sort live in the URL
  const list = useListSearchParams({
    sortValues: SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const invitePage = useAdminInvitePage({
    page: list.page,
    page_size: PAGE_SIZE,
    search: list.search || undefined,
    sort_by: list.sortBy,
    sort_direction: list.sortDirection,
  })

  return (
    <div className="flex flex-col gap-6">
      <AdminSectionNav canReadInvites />
      <h1 className="text-xl font-extrabold">Invites</h1>
      {canCreateInvites && (
        <div className="max-w-xl">
          <CreateInviteForm />
        </div>
      )}
      <ListSearchBox label="Search invites" value={list.search} onChange={list.setSearch} />
      <DataTable
        columns={buildAdminInviteColumns(canCreateInvites)}
        rows={invitePage.data?.invites}
        getRowKey={(invite) => invite.identity}
        sortBy={list.sortBy}
        sortDirection={list.sortDirection}
        onSortChange={list.setSort}
        isPending={invitePage.isPending}
        error={invitePage.error}
        isNarrowed={list.search !== ''}
        emptyMessage="No invites yet."
        noMatchMessage="No invites match your search."
        pagination={invitePage.data?.pagination}
        onPageChange={list.setPage}
      />
      {invitePage.data && (
        <ListPager pagination={invitePage.data.pagination} onPageChange={list.setPage} />
      )}
    </div>
  )
}
