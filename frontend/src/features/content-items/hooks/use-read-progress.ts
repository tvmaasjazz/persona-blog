import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

import type { components } from '@/lib/api-schema.gen'

export type ReadProgress = components['schemas']['RecordContentItemViewDto']['read_percent']

// Returns the furthest quarter of the element the bottom of the viewport has passed.
export function useReadProgress(elementRef: RefObject<HTMLElement | null>): ReadProgress {
  const [furthestProgress, setFurthestProgress] = useState<ReadProgress>(0)

  useEffect(() => {
    let frameId = 0

    function measure() {
      frameId = 0
      const element = elementRef.current
      if (!element) {
        return
      }

      // How far the viewport's bottom is into the element; a post that fits counts as all
      const { top, height } = element.getBoundingClientRect()
      const fractionRead = height > 0 ? (window.innerHeight - top) / height : 1
      const quarter = Math.min(4, Math.max(0, Math.floor(fractionRead * 4)))
      const progress = (quarter * 25) as ReadProgress

      // Never go down
      setFurthestProgress((previous) => (progress > previous ? progress : previous))
    }

    function scheduleMeasure() {
      if (frameId === 0) {
        frameId = requestAnimationFrame(measure)
      }
    }

    measure()
    window.addEventListener('scroll', scheduleMeasure, { passive: true })
    window.addEventListener('resize', scheduleMeasure, { passive: true })

    return () => {
      window.removeEventListener('scroll', scheduleMeasure)
      window.removeEventListener('resize', scheduleMeasure)
      cancelAnimationFrame(frameId)
    }
  }, [elementRef])

  return furthestProgress
}
