import type { components } from '@/lib/api-schema.gen'

type CreditLedgerEntryType = components['schemas']['CreditLedgerEntryType']

function toSentenceCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase()
}

export function formatLedgerEntryType(entryType: CreditLedgerEntryType): string {
  return toSentenceCase(entryType)
}
