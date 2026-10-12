import { useEffect, useRef } from 'react'
import { useBlocker } from 'react-router'

// Asks before leaving a finished run that hasn't been saved: an in-app navigation is
// held by the returned blocker, and closing or reloading the tab gets the browser's own
// prompt. allowLeave lets a deliberate exit through, such as saving or discarding.
export function useUnsavedRunGuard(isGuarded: boolean) {
  // A ref, not state: allowLeave runs right before navigate, so the blocker has to
  // see the change without waiting for a render.
  const isLeaveAllowedRef = useRef(false)

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isGuarded && !isLeaveAllowedRef.current && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!isGuarded) {
      return
    }
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      if (!isLeaveAllowedRef.current) {
        event.preventDefault()
      }
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [isGuarded])

  function allowLeave() {
    isLeaveAllowedRef.current = true
  }

  return { blocker, allowLeave }
}
