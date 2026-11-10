import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { components } from '@/lib/api-schema.gen'

type ListPagerProps = {
  pagination: components['schemas']['PaginationResponseDto']
  onPageChange: (page: number) => void
}

export function ListPager({ pagination, onPageChange }: ListPagerProps) {
  const pageCount = Math.max(1, Math.ceil(pagination.total / pagination.page_size))

  if (pageCount <= 1) {
    return null
  }

  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-4">
      <Button
        variant="secondary"
        disabled={pagination.page <= 1}
        onClick={() => onPageChange(pagination.page - 1)}
      >
        <ChevronLeft aria-hidden />
        <span className="sr-only sm:not-sr-only">Previous</span>
      </Button>
      <p className="text-sm whitespace-nowrap text-muted-foreground">
        Page {pagination.page} of {pageCount}
      </p>
      <Button
        variant="secondary"
        disabled={pagination.page >= pageCount}
        onClick={() => onPageChange(pagination.page + 1)}
      >
        <span className="sr-only sm:not-sr-only">Next</span>
        <ChevronRight aria-hidden />
      </Button>
    </nav>
  )
}
