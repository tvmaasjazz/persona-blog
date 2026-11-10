import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

// Refetches the current user's balance when a run's status changes, since the run charges it.
export function useRunBalanceRefresh(runStatus: string) {
  const queryClient = useQueryClient()
  const previousStatusRef = useRef(runStatus)

  useEffect(() => {
    if (previousStatusRef.current === runStatus) {
      return
    }
    previousStatusRef.current = runStatus
    void queryClient.invalidateQueries({ queryKey: ['users', 'me'] })
  }, [queryClient, runStatus])
}
