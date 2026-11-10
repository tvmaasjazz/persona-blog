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
import {
  CREDIT_LEDGER_COLUMNS,
  CREDIT_LEDGER_SORT_VALUES,
} from '@/features/admin/components/credit-ledger-columns'
import { GrantCreditsForm } from '@/features/admin/components/grant-credits-form'
import { UserAccountCard } from '@/features/admin/components/user-account-card'
import { UserActiveControl } from '@/features/admin/components/user-active-control'
import { UserRoleControl } from '@/features/admin/components/user-role-control'
import { useCurrentUser } from '@/features/auth/api/current-user-query'
import { hasPermission } from '@/features/auth/permissions'
import { useListSearchParams } from '@/lib/use-list-search-params'

const LEDGER_PAGE_SIZE = 20

export function AdminUserPage() {
  const { userIdentity = '' } = useParams()
  const { data: currentUser } = useCurrentUser()
  const adminUser = useAdminUser(userIdentity)
  const list = useListSearchParams({
    sortValues: CREDIT_LEDGER_SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const ledgerPage = useAdminCreditLedgerPage(userIdentity, {
    page: list.page,
    page_size: LEDGER_PAGE_SIZE,
    search: list.search || undefined,
    sort_by: list.sortBy,
    sort_direction: list.sortDirection,
  })

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
  const isOwnAccount = user !== undefined && user.identity === currentUser?.identity

  // Section nav and title as the header; the account and write controls as the sidebar
  return (
    <PageWithSidebar
      header={
        <div className="flex flex-col gap-4">
          <AdminSectionNav canReadInvites={hasPermission(currentUser, 'INVITE_READ')} />
          <h1 className="text-xl font-extrabold break-all">{user?.email ?? 'User'}</h1>
        </div>
      }
      sidebar={
        user ? (
          <>
            <UserAccountCard user={user} />
            <GrantCreditsForm userIdentity={user.identity} isOwnAccount={isOwnAccount} />
            {user.role === 'ADMIN' ? (
              <p className="text-sm text-muted-foreground">
                An admin's role is changed in the database.
              </p>
            ) : (
              <>
                <UserRoleControl
                  userIdentity={user.identity}
                  userEmail={user.email}
                  isCreator={user.role === 'CREATOR'}
                  isOwnAccount={isOwnAccount}
                />
                <UserActiveControl
                  userIdentity={user.identity}
                  userEmail={user.email}
                  isActive={user.is_active}
                  isOwnAccount={isOwnAccount}
                />
              </>
            )}
          </>
        ) : (
          <CardListSkeleton />
        )
      }
    >
      {/* The ledger */}
      <div className="flex flex-col gap-4">
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
        />
        {ledgerPage.data && (
          <ListPager pagination={ledgerPage.data.pagination} onPageChange={list.setPage} />
        )}
      </div>
    </PageWithSidebar>
  )
}
