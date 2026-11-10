import type { DataTableColumn } from '@/components/data-table'
import type { components } from '@/lib/api-schema.gen'
import { formatDateTime } from '@/lib/format-date'
import { formatLedgerUsd } from '@/lib/format-usd'

type AdminCreditLedgerEntryResponseDto = components['schemas']['AdminCreditLedgerEntryResponseDto']
type CreditLedgerSort = 'CREATED_AT'

export const CREDIT_LEDGER_SORT_VALUES: readonly CreditLedgerSort[] = ['CREATED_AT']

export const CREDIT_LEDGER_COLUMNS: DataTableColumn<
  AdminCreditLedgerEntryResponseDto,
  CreditLedgerSort
>[] = [
  {
    header: 'Date',
    sortValue: 'CREATED_AT',
    className: 'whitespace-nowrap',
    cell: (entry) => formatDateTime(entry.created_at),
  },
  {
    header: 'Type',
    className: 'capitalize',
    cell: (entry) => entry.entry_type.toLowerCase(),
  },
  {
    header: 'Amount',
    className: 'text-right whitespace-nowrap',
    cell: (entry) => formatLedgerUsd(entry.amount_usd),
  },
  {
    header: 'Note',
    className: 'min-w-48 break-words whitespace-normal',
    cell: (entry) => entry.note ?? '',
  },
  {
    header: 'Made by',
    className: 'break-all',
    cell: (entry) => entry.created_by_email,
  },
]
