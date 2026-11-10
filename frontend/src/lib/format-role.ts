import type { components } from '@/lib/api-schema.gen'

type RoleType = components['schemas']['RoleType']
type CreditLedgerEntryType = components['schemas']['CreditLedgerEntryType']

function toSentenceCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase()
}

export function formatRole(role: RoleType): string {
  return toSentenceCase(role)
}

export function formatLedgerEntryType(entryType: CreditLedgerEntryType): string {
  return toSentenceCase(entryType)
}
