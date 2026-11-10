// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useReadProgress } from './use-read-progress'

const VIEWPORT_HEIGHT = 800
const POST_HEIGHT = 4000

// Where the post's top sits when the viewport's bottom is that far into it
function topAtFractionRead(fractionRead: number) {
  return VIEWPORT_HEIGHT - fractionRead * POST_HEIGHT
}

function renderReadProgress({ top, height }: { top: number; height: number }) {
  const postElement = document.createElement('div')
  const postBox = { top, height }
  vi.spyOn(postElement, 'getBoundingClientRect').mockImplementation(
    () => new DOMRect(0, postBox.top, 600, postBox.height),
  )
  const rendered = renderHook(() => useReadProgress({ current: postElement }))

  // Moves the post as a scroll would, then lets the throttled measure run
  function scrollPostTo(nextTop: number) {
    postBox.top = nextTop
    act(() => {
      window.dispatchEvent(new Event('scroll'))
      vi.advanceTimersToNextFrame()
    })
  }

  return { result: rendered.result, unmount: rendered.unmount, scrollPostTo }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(VIEWPORT_HEIGHT)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('useReadProgress', () => {
  it('reads 0 at the top of a long post', () => {
    const { result } = renderReadProgress({ top: 200, height: POST_HEIGHT })

    expect(result.current).toBe(0)
  })

  it('moves to each quarter only once the viewport bottom reaches it', () => {
    const { result, scrollPostTo } = renderReadProgress({ top: 200, height: POST_HEIGHT })

    for (const progress of [25, 50, 75, 100]) {
      const fractionRead = progress / 100
      scrollPostTo(topAtFractionRead(fractionRead) + 1)
      expect(result.current).toBe(progress - 25)
      scrollPostTo(topAtFractionRead(fractionRead))
      expect(result.current).toBe(progress)
    }
  })

  it('jumps straight to 100 when scrolled past the end', () => {
    const { result, scrollPostTo } = renderReadProgress({ top: 200, height: POST_HEIGHT })

    scrollPostTo(topAtFractionRead(1.5))

    expect(result.current).toBe(100)
  })

  it('never goes down when scrolled back up', () => {
    const { result, scrollPostTo } = renderReadProgress({ top: 200, height: POST_HEIGHT })

    scrollPostTo(topAtFractionRead(0.8))
    scrollPostTo(200)

    expect(result.current).toBe(75)
  })

  it('reads a post that fits the viewport as 100 at once', () => {
    const { result } = renderReadProgress({ top: 100, height: 300 })

    expect(result.current).toBe(100)
  })

  it('reads a post with no height as 100, even below the viewport', () => {
    const { result } = renderReadProgress({ top: VIEWPORT_HEIGHT + 100, height: 0 })

    expect(result.current).toBe(100)
  })

  it('measures again when the window is resized', () => {
    const { result } = renderReadProgress({ top: 200, height: POST_HEIGHT })
    expect(result.current).toBe(0)

    // A taller viewport reaches half of the post
    vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(200 + POST_HEIGHT / 2)
    act(() => {
      window.dispatchEvent(new Event('resize'))
      vi.advanceTimersToNextFrame()
    })

    expect(result.current).toBe(50)
  })

  it('stops listening for scroll and resize after unmount', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { unmount } = renderReadProgress({ top: 200, height: POST_HEIGHT })

    unmount()

    for (const eventName of ['scroll', 'resize']) {
      const added = addSpy.mock.calls.find(([name]) => name === eventName)
      const removed = removeSpy.mock.calls.find(([name]) => name === eventName)
      expect(added).toBeDefined()
      expect(removed?.[1]).toBe(added?.[1])
    }
  })
})
