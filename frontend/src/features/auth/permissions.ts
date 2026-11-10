import type { components } from '@/lib/api-schema.gen'

type PermissionType = components['schemas']['PermissionType']
type UserResponseDto = components['schemas']['UserResponseDto']

export function hasPermission(
  user: UserResponseDto | null | undefined,
  permission: PermissionType,
): boolean {
  return user?.permissions.includes(permission) ?? false
}
