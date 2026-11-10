import { DataTable } from '@/components/data-table'
import { ListPager } from '@/components/list-pager'
import { ListSearchBox } from '@/components/list-search-box'
import { useAdminUserPage } from '@/features/admin/api/admin-user-page-query'
import { AdminSectionNav } from '@/features/admin/components/admin-section-nav'
import { ADMIN_USER_COLUMNS } from '@/features/admin/components/admin-user-columns'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'
import { useListSearchParams } from '@/lib/use-list-search-params'

const PAGE_SIZE = 20
const SORT_VALUES = [
  'CREATED_AT',
  'EMAIL',
  'LAST_ACTIVITY_AT',
] as const satisfies readonly components['schemas']['AdminUserSortType'][]

export function AdminUsersPage() {
  const { data: currentUser } = useCurrentUser()
  // Page, search and sort live in the URL
  const list = useListSearchParams({
    sortValues: SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const userPage = useAdminUserPage({
    page: list.page,
    page_size: PAGE_SIZE,
    search: list.search || undefined,
    sort_by: list.sortBy,
    sort_direction: list.sortDirection,
  })

  return (
    <div className="flex flex-col gap-6">
      <AdminSectionNav canReadInvites={hasPermission(currentUser, 'INVITE_READ')} />
      <h1 className="text-xl font-extrabold">Users</h1>
      <ListSearchBox label="Search users" value={list.search} onChange={list.setSearch} />
      <DataTable
        columns={ADMIN_USER_COLUMNS}
        rows={userPage.data?.users}
        getRowKey={(user) => user.identity}
        sortBy={list.sortBy}
        sortDirection={list.sortDirection}
        onSortChange={list.setSort}
        isPending={userPage.isPending}
        error={userPage.error}
        isNarrowed={list.search !== ''}
        emptyMessage="No users yet."
        noMatchMessage="No users match your search."
      />
      {userPage.data && (
        <ListPager pagination={userPage.data.pagination} onPageChange={list.setPage} />
      )}
    </div>
  )
}
