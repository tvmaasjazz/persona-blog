import { execFileSync } from 'node:child_process'
import path from 'node:path'

import { test as base, type BrowserContext } from '@playwright/test'

// The seeded users (backend/scripts/dev_seed.py), one per case a flow signs in as
export const SEEDED_USER_EMAILS = {
  admin: 'dev-admin@example.com',
  creator: 'dev-creator@example.com',
  lowBalanceCreator: 'dev-low@example.com',
  brokeCreator: 'dev-broke@example.com',
  reader: 'dev-reader@example.com',
  newcomer: 'dev-newcomer@example.com',
} as const

export type SeededUser = keyof typeof SEEDED_USER_EMAILS

const BACKEND_DIRECTORY = path.resolve(import.meta.dirname, '../../backend')

// Mints a fresh session for a seeded user, as Google sign-in would; dev_session refuses
// anything but a local development database
function mintSessionId(seededUser: SeededUser): string {
  const output = execFileSync(
    'uv',
    ['run', 'python', '-m', 'scripts.dev_session', '--email', SEEDED_USER_EMAILS[seededUser]],
    { cwd: BACKEND_DIRECTORY, encoding: 'utf8' },
  )
  return output.trim()
}

type SignInFixtures = {
  signInAs: (seededUser: SeededUser) => Promise<void>
}

export const test = base.extend<SignInFixtures>({
  signInAs: async ({ context }, use) => {
    await use(async (seededUser) => {
      await setSessionCookie(context, mintSessionId(seededUser))
    })
  },
})

async function setSessionCookie(context: BrowserContext, sessionId: string) {
  await context.addCookies([
    { name: 'sid', value: sessionId, domain: 'localhost', path: '/', httpOnly: true },
  ])
}

export { expect } from '@playwright/test'
