import { z } from 'zod'

export const MAX_CREDIT_GRANT_USD = 100

// Mirrors CreditGrantAmountUsdDecimal in the backend's admin dtos, held to cents.
export const creditAmountUsdSchema = z
  .string()
  .trim()
  .min(1, 'Amount is required')
  .regex(/^\d+(\.\d{1,2})?$/, 'Amount must be a number with up to two decimals')
  .refine((amount) => Number(amount) > 0, 'Amount must be more than $0')
  .refine(
    (amount) => Number(amount) <= MAX_CREDIT_GRANT_USD,
    `Amount must be $${MAX_CREDIT_GRANT_USD} or less`,
  )
