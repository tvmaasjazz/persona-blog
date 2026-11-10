import { describe, expect, it } from 'vitest'

import { formatLedgerUsd, formatUsd } from '@/lib/format-usd'

describe('formatUsd', () => {
  it('shows a balance to cents', () => {
    expect(formatUsd('5.0000000000')).toBe('$5.00')
  })

  it('rounds half away from zero', () => {
    expect(formatUsd('0.415')).toBe('$0.42')
    expect(formatUsd('-0.415')).toBe('-$0.42')
  })

  it('reads a zero sent as an exponent as zero, with no sign', () => {
    expect(formatUsd('0E-10')).toBe('$0.00')
    expect(formatUsd('-0.001')).toBe('$0.00')
  })

  it('keeps every digit of a large amount, with no float rounding', () => {
    expect(formatUsd('12345678901234567.89')).toBe('$12345678901234567.89')
  })

  it('returns text it cannot read as it came', () => {
    expect(formatUsd('not a number')).toBe('not a number')
  })
})

describe('formatLedgerUsd', () => {
  it('shows a ledger amount to four places with its sign', () => {
    expect(formatLedgerUsd('2')).toBe('+$2.0000')
    expect(formatLedgerUsd('-0.00059')).toBe('-$0.0006')
  })
})
