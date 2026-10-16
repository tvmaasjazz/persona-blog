import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { describeRunReady } from '@/features/generate-text/run-steps'
import type { components } from '@/lib/api-schema.gen'

type GenerateTextRunResponseDto = components['schemas']['GenerateTextRunResponseDto']

function isWorking(status: string | undefined) {
  return status === 'PENDING' || status === 'RUNNING'
}

// Tells the user when a run they are watching stops working: a toast, and back to the
// top so the new text is in view. A run that loads already paused or finished is silent.
export function useRunReadyNotice(run: GenerateTextRunResponseDto) {
  const previousStatusRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    const wasWorking = isWorking(previousStatusRef.current)
    previousStatusRef.current = run.status
    if (!wasWorking || isWorking(run.status)) {
      return
    }
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
