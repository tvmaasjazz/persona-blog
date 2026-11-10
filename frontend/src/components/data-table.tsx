import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { ReactNode } from 'react'

import { QueryErrorState } from '@/components/query-error-state'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { components } from '@/lib/api-schema.gen'
import { cn } from '@/lib/utils'

type SortDirection = components['schemas']['SortDirectionType']

const SKELETON_ROW_COUNT = 5

export type DataTableColumn<TRow, TSort extends string> = {
  header: string
  cell: (row: TRow) => ReactNode
  // Given, the header sorts by this value
  sortValue?: TSort
  // The direction a first click sorts by; DESC when not given
  firstSortDirection?: SortDirection
  // Width and alignment classes for the header and its cells, like `w-40 text-right`
  className?: string
}

type DataTableProps<TRow, TSort extends string> = {
  columns: DataTableColumn<TRow, TSort>[]
  rows: TRow[] | undefined
  getRowKey: (row: TRow) => string
  sortBy: TSort
  sortDirection: SortDirection
  onSortChange: (sortBy: TSort, sortDirection: SortDirection) => void
  isPending: boolean
  error: Error | null
  // Whether a search or filter is narrowing the rows
  isNarrowed: boolean
  emptyMessage: string
  noMatchMessage: string
}

export function DataTable<TRow, TSort extends string>({
  columns,
  rows,
  getRowKey,
  sortBy,
  sortDirection,
  onSortChange,
  isPending,
  error,
  isNarrowed,
  emptyMessage,
  noMatchMessage,
}: DataTableProps<TRow, TSort>) {
  // Clicking the sorted column flips it; another column starts at its natural order
  function handleSort(column: DataTableColumn<TRow, TSort>, sortValue: TSort) {
    if (sortValue === sortBy) {
      onSortChange(sortValue, sortDirection === 'ASC' ? 'DESC' : 'ASC')
      return
    }
    onSortChange(sortValue, column.firstSortDirection ?? 'DESC')
  }

  if (error) {
    return <QueryErrorState error={error} />
  }

  if (!isPending && rows?.length === 0) {
    return <p className="text-muted-foreground">{isNarrowed ? noMatchMessage : emptyMessage}</p>
  }

  // Header row, then skeleton or data rows
  return (
    <div className="rounded-2xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => {
              const sortValue = column.sortValue
              const isSorted = sortValue !== undefined && sortValue === sortBy
              const SortIcon = isSorted
                ? sortDirection === 'ASC'
                  ? ArrowUp
                  : ArrowDown
                : ArrowUpDown

              return (
                <TableHead
                  key={column.header}
                  className={column.className}
                  aria-sort={
                    isSorted ? (sortDirection === 'ASC' ? 'ascending' : 'descending') : undefined
                  }
                >
                  {sortValue === undefined ? (
                    column.header
                  ) : (
                    <Button
                      variant="ghost"
                      className="-ml-3 h-8 px-3"
                      onClick={() => handleSort(column, sortValue)}
                    >
                      {column.header}
                      <SortIcon aria-hidden className={cn(!isSorted && 'opacity-50')} />
                    </Button>
                  )}
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isPending
            ? Array.from({ length: SKELETON_ROW_COUNT }, (_unused, index) => (
                <TableRow key={index} aria-hidden>
                  {columns.map((column) => (
                    <TableCell key={column.header} className={column.className}>
                      <div className="h-5 rounded-lg bg-accent" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            : rows?.map((row) => (
                <TableRow key={getRowKey(row)}>
                  {columns.map((column) => (
                    <TableCell key={column.header} className={column.className}>
                      {column.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
        </TableBody>
      </Table>
    </div>
  )
}
