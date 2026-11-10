import type { DataTableColumn } from '@/components/data-table'
import type { components } from '@/lib/api-schema.gen'
import { formatDateTime } from '@/lib/format-date'
import { formatLedgerEntryType } from '@/lib/format-role'
import { formatLedgerUsd } from '@/lib/format-usd'

type AdminCreditLedgerEntryResponseDto = components['schemas']['AdminCreditLedgerEntryResponseDto']
type CreditLedgerSort = components['schemas']['AdminCreditLedgerSortType']

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
    cell: (entry) => formatLedgerEntryType(entry.entry_type),
  },
  {
    header: 'Amount',
    className: 'text-right whitespace-nowrap',
    cell: (entry) => formatLedgerUsd(entry.amount_usd),
  },
  {
    header: 'Note',
    className: 'min-w-32 break-words whitespace-normal',
    cell: (entry) => entry.note ?? '',
  },
  {
    header: 'Made by',
    className: 'min-w-32 break-all whitespace-normal',
    cell: (entry) => entry.created_by_email,
  },
]
