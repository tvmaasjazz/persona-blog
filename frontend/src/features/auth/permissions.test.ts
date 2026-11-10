import { describe, expect, it } from 'vitest'

import { hasPermission } from '@/features/auth/permissions'
import type { components } from '@/lib/api-schema.gen'

type UserResponseDto = components['schemas']['UserResponseDto']

function buildUser(permissions: UserResponseDto['permissions']): UserResponseDto {
  return {
    identity: '00000000-0000-0000-0000-000000000001',
    email: 'reader@example.com',
    display_name: null,
    avatar_url: null,
    role: 'READER',
    permissions,
    credit_balance_usd: '0',
    is_credit_balance_low: false,
  }
}

describe('hasPermission', () => {
  it('is true for a user who holds the permission', () => {
    const user = buildUser(['PERSONA_READ', 'PERSONA_WRITE'])

    expect(hasPermission(user, 'PERSONA_WRITE')).toBe(true)
  })

  it('is false for a user who lacks the permission', () => {
    const user = buildUser(['PERSONA_READ', 'BLOG_POST_READ'])

    expect(hasPermission(user, 'PERSONA_WRITE')).toBe(false)
  })

  it('is false for a signed-out user', () => {
    expect(hasPermission(null, 'PERSONA_READ')).toBe(false)
  })

  it('is false while the user is still loading', () => {
    expect(hasPermission(undefined, 'PERSONA_READ')).toBe(false)
  })
})
