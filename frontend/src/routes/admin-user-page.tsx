import { useParams } from 'react-router'

import { CardListSkeleton } from '@/components/card-list-skeleton'
import { DataTable } from '@/components/data-table'
import { PageWithSidebar } from '@/components/layout/page-with-sidebar'
import { ListPager } from '@/components/list-pager'
import { ListSearchBox } from '@/components/list-search-box'
import { QueryErrorState } from '@/components/query-error-state'
import { useAdminCreditLedgerPage } from '@/features/admin/api/admin-credit-ledger-page-query'
import { useAdminUser } from '@/features/admin/api/admin-user-query'
import { AdminSectionNav } from '@/features/admin/components/admin-section-nav'
import { AdminUserSidebar } from '@/features/admin/components/admin-user-sidebar'
import { CREDIT_LEDGER_COLUMNS } from '@/features/admin/components/credit-ledger-columns'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'
import { useListSearchParams } from '@/lib/use-list-search-params'

const LEDGER_PAGE_SIZE = 20
const LEDGER_SORT_VALUES = [
  'CREATED_AT',
] as const satisfies readonly components['schemas']['AdminCreditLedgerSortType'][]

export function AdminUserPage() {
  const { userIdentity = '' } = useParams()
  const { data: currentUser } = useCurrentUser()
  const adminUser = useAdminUser(userIdentity)
  const list = useListSearchParams({
    sortValues: LEDGER_SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const canReadLedger = hasPermission(currentUser, 'CREDIT_READ')
  const ledgerPage = useAdminCreditLedgerPage(
    userIdentity,
    {
      page: list.page,
      page_size: LEDGER_PAGE_SIZE,
      search: list.search || undefined,
      sort_by: list.sortBy,
      sort_direction: list.sortDirection,
    },
    canReadLedger,
  )

  // Not found, or another failure, in place of the page
  if (adminUser.error) {
    return (
      <QueryErrorState
        error={adminUser.error}
        notFoundMessage="User not found."
        backTo={{ to: '/admin/users', label: 'Back to users' }}
      />
    )
  }

  const user = adminUser.data

  // Section nav and title as the header; the account and write controls as the sidebar
  return (
    <PageWithSidebar
      header={
        <div className="flex flex-col gap-4">
          <AdminSectionNav canReadInvites={hasPermission(currentUser, 'INVITE_READ')} />
          <h1 className="text-xl font-extrabold wrap-anywhere">{user?.email ?? 'User'}</h1>
        </div>
      }
      sidebar={
        user ? (
          <AdminUserSidebar
            user={user}
            canGrantCredits={hasPermission(currentUser, 'CREDIT_WRITE')}
            canChangeUser={hasPermission(currentUser, 'USER_WRITE')}
          />
        ) : (
          <CardListSkeleton />
        )
      }
    >
      {/* The ledger, for those who can read it */}
      {canReadLedger && (
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-bold">Credit ledger</h2>
          <ListSearchBox label="Search the ledger" value={list.search} onChange={list.setSearch} />
          <DataTable
            columns={CREDIT_LEDGER_COLUMNS}
            rows={ledgerPage.data?.credit_ledger_entries}
            getRowKey={(entry) => entry.identity}
            sortBy={list.sortBy}
            sortDirection={list.sortDirection}
            onSortChange={list.setSort}
            isPending={ledgerPage.isPending}
            error={ledgerPage.error}
            isNarrowed={list.search !== ''}
            emptyMessage="No credit activity yet."
            noMatchMessage="No entries match your search."
            pagination={ledgerPage.data?.pagination}
            onPageChange={list.setPage}
          />
          {ledgerPage.data && (
            <ListPager pagination={ledgerPage.data.pagination} onPageChange={list.setPage} />
          )}
        </div>
      )}
    </PageWithSidebar>
  )
}
