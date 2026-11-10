import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import { formatDate, formatDateTime } from '@/lib/format-date'

// The functions use the runtime's time zone, so pin it; the locale comes from LANG (en-US here)
beforeAll(() => {
  vi.stubEnv('TZ', 'UTC')
})

afterAll(() => {
  vi.unstubAllEnvs()
})

describe('formatDate', () => {
  it('shows the date with a short month name', () => {
    expect(formatDate('2026-03-05T14:07:00Z')).toBe('Mar 5, 2026')
  })

  it('shows the date in the local time zone, not the one the time was sent in', () => {
    expect(formatDate('2026-03-05T23:30:00-05:00')).toBe('Mar 6, 2026')
  })
})

describe('formatDateTime', () => {
  it('shows the date and the time to the minute', () => {
    expect(formatDateTime('2026-03-05T14:07:59Z')).toBe('Mar 5, 2026, 2:07 PM')
  })

  it('shows a time just before midnight on the same day', () => {
    expect(formatDateTime('2026-03-05T23:30:00Z')).toBe('Mar 5, 2026, 11:30 PM')
  })
})
