import type { Page } from '@playwright/test'

import type { components } from '../src/lib/api-schema.gen.ts'
import { expect, SEEDED_USER_EMAILS, test } from './fixtures.ts'

type AdminUserResponse = components['schemas']['AdminUserResponseDto']
type AdminUserPageResponse = components['schemas']['AdminUserPageResponseDto']
type AdminInvitePageResponse = components['schemas']['AdminInvitePageResponseDto']

const NEWCOMER_EMAIL = SEEDED_USER_EMAILS.newcomer
const ADMIN_EMAIL = SEEDED_USER_EMAILS.admin

// The seeded emails in the order an ascending email sort puts them
const SEEDED_EMAILS_ASCENDING = [
  'dev-admin@example.com',
  'dev-broke@example.com',
  'dev-creator@example.com',
  'dev-invited@example.com',
  'dev-low@example.com',
  'dev-newcomer@example.com',
  'dev-reader@example.com',
  'dev-suspended@example.com',
]

// Reads the newcomer from the API
async function findNewcomer(page: Page): Promise<AdminUserResponse> {
  const response = await page.request.get('/api/admin/users', {
    params: { search: NEWCOMER_EMAIL },
  })
  expect(response.ok()).toBe(true)
  const userPage: AdminUserPageResponse = await response.json()
  const newcomer = userPage.users.find((user) => user.email === NEWCOMER_EMAIL)
  if (newcomer === undefined) {
    throw new Error(`The seed has no ${NEWCOMER_EMAIL}`)
  }
  return newcomer
}

// Puts the newcomer back to the seed's reader who is active, whatever state they are in
async function restoreNewcomer(page: Page) {
  const newcomer = await findNewcomer(page)
  if (newcomer.role !== 'READER') {
    const roleResponse = await page.request.put(`/api/admin/users/${newcomer.identity}/role`, {
      data: { role: 'READER' },
    })
    expect(roleResponse.ok()).toBe(true)
  }
  if (!newcomer.is_active) {
    const activeResponse = await page.request.put(`/api/admin/users/${newcomer.identity}/active`, {
      data: { is_active: true },
    })
    expect(activeResponse.ok()).toBe(true)
  }
}

// Searches the users table for the newcomer and opens their page
async function openNewcomerPage(page: Page) {
  await page.goto('/admin/users')
  await page.getByRole('searchbox', { name: 'Search users' }).fill(NEWCOMER_EMAIL)
  await page.getByRole('link', { name: NEWCOMER_EMAIL }).click()
  await expect(page.getByRole('heading', { level: 1, name: NEWCOMER_EMAIL })).toBeVisible()
}

// The seeded emails the table shows, in the order it shows them
async function readSeededEmailsInOrder(page: Page): Promise<string[]> {
  const emails = await page.getByRole('cell').getByRole('link').allInnerTexts()
  return emails.filter((email) => SEEDED_EMAILS_ASCENDING.includes(email))
}

test('the admin sorts the users table by email and searches it', async ({ page, signInAs }) => {
  await signInAs('admin')
  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { level: 1, name: 'Users' })).toBeVisible()

  // Newest sign-ups first until a column is chosen
  const emailHeader = page.getByRole('columnheader', { name: 'Email' })
  const joinedHeader = page.getByRole('columnheader', { name: 'Joined' })
  await expect(joinedHeader).toHaveAttribute('aria-sort', 'descending')
  await expect(page.getByRole('link', { name: NEWCOMER_EMAIL })).toBeVisible()

  // Sorting by email goes A to Z first
  await emailHeader.getByRole('button').click()
  await expect(emailHeader).toHaveAttribute('aria-sort', 'ascending')
  await expect(joinedHeader).not.toHaveAttribute('aria-sort')
  await expect.poll(() => readSeededEmailsInOrder(page)).toEqual(SEEDED_EMAILS_ASCENDING)

  // A second click reverses it
  await emailHeader.getByRole('button').click()
  await expect(emailHeader).toHaveAttribute('aria-sort', 'descending')
  await expect
    .poll(() => readSeededEmailsInOrder(page))
    .toEqual([...SEEDED_EMAILS_ASCENDING].reverse())

  // A search narrows the table to the match
  await page.getByRole('searchbox', { name: 'Search users' }).fill(NEWCOMER_EMAIL)
  await expect(page.getByRole('cell').getByRole('link')).toHaveText([NEWCOMER_EMAIL])

  // A search with no match says so
  await page.getByRole('searchbox', { name: 'Search users' }).fill('no-such-user-zzzz')
  await expect(page.getByText('No users match your search.')).toBeVisible()
})

test('a grant to the newcomer shows on their ledger and balance', async ({ page, signInAs }) => {
  await signInAs('admin')
  const grantNote = `e2e admin grant ${Date.now()}`

  // An earlier failed run may have left the newcomer a creator
  await restoreNewcomer(page)

  // Read the balance before the grant, from the users table
  await page.goto('/admin/users')
  await page.getByRole('searchbox', { name: 'Search users' }).fill(NEWCOMER_EMAIL)
  const newcomerRow = page.getByRole('row', { name: new RegExp(NEWCOMER_EMAIL) })
  await expect(newcomerRow).toBeVisible()
  const balanceBefore = Number((await newcomerRow.getByRole('cell').nth(3).innerText()).slice(1))
  await page.getByRole('link', { name: NEWCOMER_EMAIL }).click()
  await expect(page.getByRole('heading', { level: 1, name: NEWCOMER_EMAIL })).toBeVisible()

  try {
    // Grant one cent with a note
    await page.getByLabel('Amount (USD)').fill('0.01')
    await page.getByLabel('Note', { exact: true }).fill(grantNote)
    await page.getByRole('button', { name: 'Grant credits' }).click()
    await expect(page.getByText('Credits granted')).toBeVisible()

    // The ledger lists it, with who made it
    const ledgerRow = page.getByRole('row', { name: new RegExp(grantNote) })
    await expect(ledgerRow).toBeVisible()
    await expect(ledgerRow.getByRole('cell').nth(2)).toHaveText('+$0.0100')
    await expect(ledgerRow.getByRole('cell').nth(4)).toHaveText(ADMIN_EMAIL)

    // The balance is a cent higher
    const balanceAfter = (balanceBefore + 0.01).toFixed(2)
    await expect(
      page.getByRole('definition').filter({ hasText: new RegExp(`^\\$${balanceAfter}$`) }),
    ).toBeVisible()
  } finally {
    // A grant makes a reader a creator; put the newcomer back as the seed has them
    await restoreNewcomer(page)
  }
})

test('the admin suspends the newcomer, then reactivates them', async ({ page, signInAs }) => {
  await signInAs('admin')
  await restoreNewcomer(page)
  await openNewcomerPage(page)

  try {
    // Suspend, confirming in the dialog
    await page.getByRole('button', { name: 'Suspend' }).click()
    const suspendDialog = page.getByRole('alertdialog', { name: `Suspend ${NEWCOMER_EMAIL}?` })
    await expect(suspendDialog).toBeVisible()
    await suspendDialog.getByRole('button', { name: 'Suspend' }).click()
    await expect(page.getByText('User suspended')).toBeVisible()
    await expect(suspendDialog).toBeHidden()

    // The account says Suspended
    await expect(page.getByRole('definition').filter({ hasText: /^Suspended$/ })).toBeVisible()
    await expect(page.getByText('This account is suspended.')).toBeVisible()

    // Reactivate, confirming in the dialog
    await page.getByRole('button', { name: 'Reactivate' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Reactivate' }).click()
    await expect(page.getByText('User reactivated')).toBeVisible()
    await expect(page.getByRole('definition').filter({ hasText: /^Active$/ })).toBeVisible()
    await expect(page.getByText('This account is active.')).toBeVisible()
  } finally {
    // Leave the newcomer active, so later flows find the seed as it was
    await restoreNewcomer(page)
  }
})

test('the admin creates an invite, sees its link only in the dialog, then revokes it', async ({
  page,
  signInAs,
}) => {
  await signInAs('admin')
  const inviteName = `E2E admin invite ${Date.now()}`
  await page.goto('/admin/invites')
  await expect(page.getByRole('heading', { level: 1, name: 'Invites' })).toBeVisible()

  try {
    // Create it
    await page.getByLabel('Name', { exact: true }).fill(inviteName)
    await page.getByLabel('Amount (USD)').fill('0.50')
    await page.getByRole('button', { name: 'Create invite' }).click()

    // Its link shows in the dialog; the check keeps the link out of the test output
    const linkDialog = page.getByRole('dialog', { name: 'Invite link' })
    await expect(linkDialog).toBeVisible()
    const inviteLink = await linkDialog.getByLabel('Invite link').inputValue()
    expect(/^https?:\/\/.+\/invite\/[^/]+$/.test(inviteLink)).toBe(true)

    // Closing drops the link, and the table lists the invite as unused
    // The dialog has two Close buttons: the footer's, then the corner icon
    await linkDialog.getByRole('button', { name: 'Close' }).first().click()
    await expect(linkDialog).toBeHidden()
    await page.getByRole('searchbox', { name: 'Search invites' }).fill(inviteName)
    const inviteRow = page.getByRole('row', { name: new RegExp(inviteName) })
    await expect(inviteRow.getByRole('cell').nth(1)).toHaveText('$0.50')
    await expect(inviteRow.getByRole('cell').nth(2)).toHaveText('Unused')

    // The link is not shown again: no field in the page or the row
    await expect(page.getByLabel('Invite link')).toHaveCount(0)
    await expect(inviteRow.getByRole('textbox')).toHaveCount(0)

    // Revoke it from the table, confirming
    await inviteRow.getByRole('button', { name: `Revoke invite ${inviteName}` }).click()
    await page
      .getByRole('alertdialog', { name: `Revoke ${inviteName}?` })
      .getByRole('button', { name: 'Revoke' })
      .click()
    await expect(page.getByText('Invite revoked')).toBeVisible()
    await expect(inviteRow.getByRole('cell').nth(2)).toHaveText('Revoked')
    await expect(inviteRow.getByRole('button')).toHaveCount(0)
  } finally {
    // Revoke the invite if the test left it unused
    const response = await page.request.get('/api/admin/invites', {
      params: { search: inviteName },
    })
    expect(response.ok()).toBe(true)
    const invitePage: AdminInvitePageResponse = await response.json()
    for (const invite of invitePage.invites) {
      if (invite.name === inviteName && invite.status === 'UNUSED') {
        const revokeResponse = await page.request.post(
          `/api/admin/invites/${invite.identity}/revoke`,
        )
        expect(revokeResponse.ok()).toBe(true)
      }
    }
  }
})
