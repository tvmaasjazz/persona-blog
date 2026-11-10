import { useScrolledIntoView } from '@/lib/use-scrolled-into-view'

type InfiniteScrollSentinelProps = {
  onReached: () => void
}

// An invisible marker at the end of a list that asks for more when it scrolls into view.
export function InfiniteScrollSentinel({ onReached }: InfiniteScrollSentinelProps) {
  const sentinelRef = useScrolledIntoView<HTMLDivElement>(onReached)

  return <div ref={sentinelRef} aria-hidden className="h-px" />
}
