import type { components } from '@/lib/api-schema.gen'

type InviteStatusType = components['schemas']['InviteStatusType']

// What the user reads for an invite that can't be used, or doesn't exist.
export const INVITE_MESSAGES = {
  USED: 'This invite has already been used.',
  EXPIRED: 'This invite has expired. Ask for a new one.',
  REVOKED: 'This invite is no longer valid. Ask for a new one.',
  NOT_FOUND: "This invite link isn't valid.",
} satisfies Record<Exclude<InviteStatusType, 'UNUSED'> | 'NOT_FOUND', string>
