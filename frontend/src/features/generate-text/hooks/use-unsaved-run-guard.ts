import { useEffect, useRef } from 'react'
import { useBlocker } from 'react-router'

// Blocks leaving an unsaved run; allowLeave lets a deliberate exit through.
export function useUnsavedRunGuard(isGuarded: boolean) {
  // A ref, not state: the blocker must see allowLeave before the next render
  const isLeaveAllowedRef = useRef(false)

  // Block in-app navigation to another page
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isGuarded && !isLeaveAllowedRef.current && currentLocation.pathname !== nextLocation.pathname,
  )

  // Prompt on tab close or reload
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
