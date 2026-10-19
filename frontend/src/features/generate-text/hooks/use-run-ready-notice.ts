import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { describeRunReady } from '@/features/generate-text/run-steps'
import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

function isWorking(status: string | undefined) {
  return status === 'PENDING' || status === 'RUNNING'
}

// Toasts and scrolls to the top when a watched run stops working.
export function useRunReadyNotice(run: GenerateTextRunResponseDto) {
  const previousStatusRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    // Only react when the run goes from working to something else
    const wasWorking = isWorking(previousStatusRef.current)
    previousStatusRef.current = run.status
    if (!wasWorking || isWorking(run.status)) {
      return
    }
    // Report the failure, or what's ready to review
    if (run.status === 'FAILED') {
      toast.error('Something went wrong while writing this post.')
      return
    }
    const runReadyMessage = describeRunReady(run)
    if (runReadyMessage) {
      toast.success(runReadyMessage)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [run])
}
