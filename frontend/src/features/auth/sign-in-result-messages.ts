import { INVITE_MESSAGES } from '@/lib/invite-messages'

// The redirect's codes aren't in the OpenAPI schema. They mirror the backend's
// SignInErrorType (libs/auth/types.py) and InviteSignInResultType (libs/invites/types.py).
const SIGN_IN_ERROR_MESSAGES: Record<string, string> = {
  ACCOUNT_SUSPENDED: 'This account is suspended.',
  EMAIL_TAKEN: 'That email already belongs to another sign-in.',
  SIGN_IN_EXPIRED: 'Sign-in took too long. Try again.',
  SIGN_IN_FAILED: "Sign-in didn't work. Try again.",
}

const INVITE_ERROR_MESSAGES: Record<string, string> = {
  INVITE_NOT_FOUND: INVITE_MESSAGES.NOT_FOUND,
  INVITE_USED: INVITE_MESSAGES.USED,
  INVITE_EXPIRED: INVITE_MESSAGES.EXPIRED,
  INVITE_REVOKED: INVITE_MESSAGES.REVOKED,
}

const GENERAL_SIGN_IN_ERROR_MESSAGE = "Sign-in didn't work. Try again."
const GENERAL_INVITE_ERROR_MESSAGE = "This invite didn't work. Ask for a new one."

export type SignInResult = {
  message: string
  // An invite error can arrive with a signed-in user, or without one
  kind: 'accepted' | 'sign-in-error' | 'invite-error'
}

// Reads the redirect's params; null when there is no code to show.
export function findSignInResult(
  searchParams: URLSearchParams,
  balanceText: string | null,
): SignInResult | null {
  const errorCode = searchParams.get('error')
  const inviteResultCode = searchParams.get('invite')
  const inviteErrorCode = searchParams.get('invite_error')

  if (errorCode !== null) {
    return {
      kind: 'sign-in-error',
      message: SIGN_IN_ERROR_MESSAGES[errorCode] ?? GENERAL_SIGN_IN_ERROR_MESSAGE,
    }
  }

  if (inviteErrorCode !== null) {
    return {
      kind: 'invite-error',
      message: INVITE_ERROR_MESSAGES[inviteErrorCode] ?? GENERAL_INVITE_ERROR_MESSAGE,
    }
  }

  if (inviteResultCode !== null) {
    if (inviteResultCode !== 'ACCEPTED') {
      return { kind: 'invite-error', message: GENERAL_INVITE_ERROR_MESSAGE }
    }
    const balanceSentence = balanceText === null ? '' : ` Your balance is ${balanceText}.`
    return {
      kind: 'accepted',
      message: `You're in. You can create personas and write posts.${balanceSentence}`,
    }
  }

  return null
}
