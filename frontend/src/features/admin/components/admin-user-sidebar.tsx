import { CreditGrantForm } from '@/features/admin/components/credit-grant-form'
import { UserAccountCard } from '@/features/admin/components/user-account-card'
import { UserActiveControl } from '@/features/admin/components/user-active-control'
import { UserRoleControl } from '@/features/admin/components/user-role-control'
import type { components } from '@/lib/api-schema.gen'

type AdminUserResponseDto = components['schemas']['AdminUserResponseDto']

type AdminUserSidebarProps = {
  user: AdminUserResponseDto
  // Whether the viewer holds CREDIT_WRITE
  canGrantCredits: boolean
  // Whether the viewer holds USER_WRITE
  canChangeUser: boolean
}

// The account and the write controls that the user's role and the viewer's permissions allow.
export function AdminUserSidebar({ user, canGrantCredits, canChangeUser }: AdminUserSidebarProps) {
  const isAdmin = user.role === 'ADMIN'

  return (
    <>
      <UserAccountCard user={user} />
      {canGrantCredits && (
        <CreditGrantForm userIdentity={user.identity} isReader={user.role === 'READER'} />
      )}
      {canChangeUser &&
        (isAdmin ? (
          <p className="text-sm text-muted-foreground">
            An admin's role is changed in the database.
          </p>
        ) : (
          <>
            <UserRoleControl
              userIdentity={user.identity}
              userEmail={user.email}
              isCreator={user.role === 'CREATOR'}
            />
            <UserActiveControl
              userIdentity={user.identity}
              userEmail={user.email}
              isActive={user.is_active}
            />
          </>
        ))}
    </>
  )
}
