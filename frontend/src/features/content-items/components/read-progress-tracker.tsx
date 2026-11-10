import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

import { useRecordContentItemView } from '../api/use-record-content-item-view'
import { useReadProgress } from '../hooks/use-read-progress'

export type ReadProgressTrackerProps = {
  contentItemIdentity: string
  children: ReactNode
}

// Sends the reader's furthest quarter of the post, each once.
export function ReadProgressTracker({ contentItemIdentity, children }: ReadProgressTrackerProps) {
  // Keyed, so opening a different post starts from a clean state
  return (
    <TrackedContent key={contentItemIdentity} contentItemIdentity={contentItemIdentity}>
      {children}
    </TrackedContent>
  )
}

function TrackedContent({ contentItemIdentity, children }: ReadProgressTrackerProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const readProgress = useReadProgress(contentRef)
  const { mutate: recordView } = useRecordContentItemView()
  // The refs outlive StrictMode's double effect, so a quarter is never sent twice
  const lastSentProgressRef = useRef(-1)

  useEffect(() => {
    if (readProgress <= lastSentProgressRef.current) {
      return
    }
    lastSentProgressRef.current = readProgress
    // A failed view is dropped: no onError, so nothing is toasted or retried
    recordView({ contentItemIdentity, readPercent: readProgress })
  }, [contentItemIdentity, readProgress, recordView])

  return <div ref={contentRef}>{children}</div>
}
