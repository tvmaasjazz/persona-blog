import { describe, expect, it } from 'vitest'

import { findSignInResult } from '@/features/auth/sign-in-result-messages'

function findResult(query: string, balanceText: string | null = null) {
  return findSignInResult(new URLSearchParams(query), balanceText)
}

describe('findSignInResult', () => {
  it.each([
    ['ACCOUNT_SUSPENDED', 'This account is suspended.'],
    ['EMAIL_TAKEN', 'That email already belongs to another sign-in.'],
    ['SIGN_IN_EXPIRED', 'Sign-in took too long. Try again.'],
    ['SIGN_IN_FAILED', "Sign-in didn't work. Try again."],
  ])('shows the message for sign-in error %s', (code, message) => {
    expect(findResult(`error=${code}`)).toEqual({ kind: 'sign-in-error', message })
  })

  it('shows the general sign-in message for an unknown error code', () => {
    expect(findResult('error=SOMETHING_NEW')).toEqual({
      kind: 'sign-in-error',
      message: "Sign-in didn't work. Try again.",
    })
  })

  it.each([
    ['INVITE_NOT_FOUND', "This invite link isn't valid."],
    ['INVITE_USED', 'This invite has already been used.'],
    ['INVITE_EXPIRED', 'This invite has expired. Ask for a new one.'],
    ['INVITE_REVOKED', 'This invite is no longer valid. Ask for a new one.'],
  ])('shows the message for invite error %s', (code, message) => {
    expect(findResult(`invite_error=${code}`)).toEqual({ kind: 'invite-error', message })
  })

  it('shows the general invite message for an unknown invite error code', () => {
    expect(findResult('invite_error=SOMETHING_NEW')).toEqual({
      kind: 'invite-error',
      message: "This invite didn't work. Ask for a new one.",
    })
  })

  it('shows the general invite message for an unknown invite result code', () => {
    expect(findResult('invite=SOMETHING_NEW')).toEqual({
      kind: 'invite-error',
      message: "This invite didn't work. Ask for a new one.",
    })
  })

  it('shows the sign-in error when an invite error comes with it', () => {
    expect(findResult('error=EMAIL_TAKEN&invite_error=INVITE_USED')).toEqual({
      kind: 'sign-in-error',
      message: 'That email already belongs to another sign-in.',
    })
  })

  it('welcomes an accepted invite with the balance it was given', () => {
    expect(findResult('invite=ACCEPTED', '$5.00')).toEqual({
      kind: 'accepted',
      message: "You're in. You can create personas and write posts. Your balance is $5.00.",
    })
  })

  it('welcomes an accepted invite without a balance when none is given', () => {
    expect(findResult('invite=ACCEPTED')).toEqual({
      kind: 'accepted',
      message: "You're in. You can create personas and write posts.",
    })
  })

  it('returns null when there is no code', () => {
    expect(findResult('')).toBeNull()
  })
})
