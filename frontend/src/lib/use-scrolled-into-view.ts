import { useEffect, useRef } from 'react'

// Returns a ref for an element; calls onReached each time the element scrolls into view.
export function useScrolledIntoView<TElement extends Element>(onReached: () => void) {
  const elementRef = useRef<TElement>(null)
  const onReachedRef = useRef(onReached)

  useEffect(() => {
    onReachedRef.current = onReached
  })

  useEffect(() => {
    const element = elementRef.current
    if (!element) {
      return
    }

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        onReachedRef.current()
      }
    })
    observer.observe(element)

    return () => observer.disconnect()
  }, [])

  return elementRef
}
