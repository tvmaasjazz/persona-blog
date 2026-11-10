import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import { formatDate, formatDateTime } from '@/lib/format-date'

// The functions use the runtime's time zone, so pin one away from UTC; the locale comes from LC_ALL in `npm run test` (en-US)
beforeAll(() => {
  vi.stubEnv('TZ', 'Asia/Tokyo')
})

afterAll(() => {
  vi.unstubAllEnvs()
})

describe('formatDate', () => {
  it('shows the date with a short month name', () => {
    expect(formatDate('2026-03-05T01:07:00Z')).toBe('Mar 5, 2026')
  })

  it('shows the local day when it differs from the UTC day', () => {
    expect(formatDate('2026-03-05T20:30:00Z')).toBe('Mar 6, 2026')
  })

  it('shows the date in the local time zone, not the one the time was sent in', () => {
    expect(formatDate('2026-03-05T10:30:00-05:00')).toBe('Mar 6, 2026')
  })
})

describe('formatDateTime', () => {
  it('shows the date and the time to the minute', () => {
    expect(formatDateTime('2026-03-05T05:07:59Z')).toBe('Mar 5, 2026, 2:07 PM')
  })

  it('shows the local day and time when the UTC day differs', () => {
    expect(formatDateTime('2026-03-05T23:30:00Z')).toBe('Mar 6, 2026, 8:30 AM')
  })
})
