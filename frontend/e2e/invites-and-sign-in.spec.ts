import type { Page } from '@playwright/test'

import type { components } from '../src/lib/api-schema.gen.ts'
import { expect, test } from './fixtures.ts'

type CreatedInvite = { identity: string; inviteCode: string }

// Creates an invite through the API with the page's session; only the code is kept, never shown
async function createInvite(page: Page): Promise<CreatedInvite> {
  const response = await page.request.post('/api/admin/invites', {
    data: { name: `E2E invite page ${Date.now()}`, credit_amount_usd: '0.50', expires_in_days: 1 },
  })
  expect(response.ok()).toBe(true)
  const body: components['schemas']['AdminInviteCreateResponseDto'] = await response.json()
  return { identity: body.identity, inviteCode: body.invite_url.split('/').pop() ?? '' }
}

async function revokeInvite(page: Page, invite: CreatedInvite) {
  const response = await page.request.post(`/api/admin/invites/${invite.identity}/revoke`)
  expect(response.ok()).toBe(true)
}

test('an unused invite link offers its credit and a Google button carrying the code', async ({
  page,
  context,
  signInAs,
}) => {
  await signInAs('admin')
  const invite = await createInvite(page)

  try {
    // Open the link signed out
    await context.clearCookies()
    await page.goto(`/invite/${invite.inviteCode}`)
    await expect(page.getByRole('heading', { level: 1, name: 'Invite' })).toBeVisible()
    await expect(
      page.getByText('This invite gives you $0.50 in credit to create personas and write posts.'),
    ).toBeVisible()

    // The button carries the code; it isn't followed
    await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute(
      'href',
      `/api/auth/google/login?invite_code=${invite.inviteCode}`,
    )
  } finally {
    // Revoke it with a fresh admin session
    await signInAs('admin')
    await revokeInvite(page, invite)
  }
})

test('a revoked invite link says it is no longer valid', async ({ page, signInAs }) => {
  await signInAs('admin')
  const invite = await createInvite(page)
  await revokeInvite(page, invite)

  await page.goto(`/invite/${invite.inviteCode}`)
  await expect(page.getByText('This invite is no longer valid. Ask for a new one.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveCount(0)
})

test('an unknown invite code says the link is not valid', async ({ page }) => {
  await page.goto('/invite/not-a-real-code')
  await expect(page.getByText("This invite link isn't valid.")).toBeVisible()
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveCount(0)
})

const SIGN_IN_MESSAGES = [
  ['error=ACCOUNT_SUSPENDED', 'This account is suspended.'],
  ['error=EMAIL_TAKEN', 'That email already belongs to another sign-in.'],
  ['error=SIGN_IN_EXPIRED', 'Sign-in took too long. Try again.'],
  ['error=SIGN_IN_FAILED', "Sign-in didn't work. Try again."],
  ['error=SOMETHING_NEW', "Sign-in didn't work. Try again."],
  ['invite_error=INVITE_NOT_FOUND', "This invite link isn't valid."],
  ['invite_error=INVITE_USED', 'This invite has already been used.'],
  ['invite_error=INVITE_EXPIRED', 'This invite has expired. Ask for a new one.'],
  ['invite_error=INVITE_REVOKED', 'This invite is no longer valid. Ask for a new one.'],
  ['invite_error=SOMETHING_NEW', "This invite didn't work. Ask for a new one."],
  ['invite=SOMETHING_NEW', "This invite didn't work. Ask for a new one."],
] as const

for (const [query, message] of SIGN_IN_MESSAGES) {
  test(`/sign-in?${query} signed out shows "${message}"`, async ({ page }) => {
    await page.goto(`/sign-in?${query}`)
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible()
    await expect(page.getByRole('alert')).toHaveText(message)
    await expect(page.getByRole('link', { name: 'Continue with Google' })).toBeVisible()
  })
}

test('an accepted invite signed out shows only the sign-in card', async ({ page }) => {
  await page.goto('/sign-in?invite=ACCEPTED')
  await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 1, name: "You're in" })).toHaveCount(0)
  await expect(page.getByRole('status')).toHaveCount(0)
})

test('an accepted invite signed in as a creator shows their balance', async ({
  page,
  signInAs,
}) => {
  await signInAs('creator')
  const meResponse = await page.request.get('/api/users/me')
  const me: components['schemas']['UserResponseDto'] = await meResponse.json()
  const balanceText = `$${Number(me.credit_balance_usd).toFixed(2)}`

  await page.goto('/sign-in?invite=ACCEPTED')
  await expect(page.getByRole('heading', { level: 1, name: "You're in" })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText(
    `You're in. You can create personas and write posts. Your balance is ${balanceText}.`,
  )
  await expect(page.getByRole('link', { name: 'Go home' })).toBeVisible()
})
