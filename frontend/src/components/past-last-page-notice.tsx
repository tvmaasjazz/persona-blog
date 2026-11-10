import { Button } from '@/components/ui/button'

type PastLastPageNoticeProps = {
  onFirstPage: () => void
}

// Says a page past the last one is empty, with a way back to page 1.
export function PastLastPageNotice({ onFirstPage }: PastLastPageNoticeProps) {
  return (
    <div className="flex flex-col items-start gap-4">
      <p className="text-muted-foreground">Nothing on this page.</p>
      <Button variant="secondary" onClick={onFirstPage}>
        Go to page 1
      </Button>
    </div>
  )
}
