const AMOUNT_PATTERN = /^([+-])?(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/

// Rounds a decimal string half away from zero with string and BigInt maths, so no float is involved.
function formatDecimal(amount: string, places: number, isPlusShown: boolean): string {
  const match = AMOUNT_PATTERN.exec(amount.trim())
  if (!match) {
    return amount
  }
  const [, sign, whole = '0', fraction = '', exponent = '0'] = match

  // Shift the decimal point by the exponent, since a zero Decimal can arrive as "0E-10"
  const digits = whole + fraction
  const pointIndex = whole.length + Number(exponent)
  const padded = pointIndex < 0 ? '0'.repeat(-pointIndex) + digits : digits.padEnd(pointIndex, '0')
  const integerLength = Math.max(pointIndex, 0)
  const integerPart = padded.slice(0, integerLength) || '0'
  const fractionPart = padded.slice(integerLength)

  // Round to the places asked for
  const kept = BigInt(integerPart + fractionPart.slice(0, places).padEnd(places, '0'))
  const roundUp = (fractionPart.charAt(places) || '0') >= '5' ? 1n : 0n
  const rounded = kept + roundUp
  const roundedText = rounded.toString().padStart(places + 1, '0')
  const text = `$${roundedText.slice(0, roundedText.length - places)}.${roundedText.slice(roundedText.length - places)}`

  // A zero has no sign
  if (rounded === 0n) {
    return text
  }
  if (sign === '-') {
    return `-${text}`
  }
  return isPlusShown ? `+${text}` : text
}

// A balance to cents, like "$0.42".
export function formatUsd(amount: string): string {
  return formatDecimal(amount, 2, false)
}

// A ledger amount to four places with its sign, like "+$0.0042".
export function formatLedgerUsd(amount: string): string {
  return formatDecimal(amount, 4, true)
}
