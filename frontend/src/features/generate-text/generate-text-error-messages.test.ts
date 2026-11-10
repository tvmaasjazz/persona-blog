import { describe, expect, it } from 'vitest'

import {
  resumeRunErrorMessage,
  startRunErrorMessage,
} from '@/features/generate-text/generate-text-error-messages'
import { ApiError } from '@/lib/api-error'

const INSUFFICIENT_CREDITS_MESSAGE =
  'Your credit balance is too low to write. Ask the admin for more credits.'

describe('startRunErrorMessage', () => {
  it('asks for more credits on a 402', () => {
    expect(startRunErrorMessage(new ApiError(402, 'Insufficient credits'))).toBe(
      INSUFFICIENT_CREDITS_MESSAGE,
    )
  })

  it('says to wait for a run to finish on a 409', () => {
    expect(startRunErrorMessage(new ApiError(409, 'Too many active runs'))).toBe(
      'You already have the most posts being written at once. Wait for one to finish.',
    )
  })

  it('shows the general message, not the detail, for another status', () => {
    expect(startRunErrorMessage(new ApiError(500, 'provider timeout: upstream 503'))).toBe(
      "Couldn't write the post. Try again.",
    )
  })

  it('shows the general message for a network failure', () => {
    expect(startRunErrorMessage(new TypeError('Failed to fetch'))).toBe(
      "Couldn't write the post. Try again.",
    )
  })
})

describe('resumeRunErrorMessage', () => {
  it('asks for more credits on a 402', () => {
    expect(resumeRunErrorMessage(new ApiError(402, 'Insufficient credits'))).toBe(
      INSUFFICIENT_CREDITS_MESSAGE,
    )
  })

  it('says the run changed or another is being written on a 409', () => {
    expect(resumeRunErrorMessage(new ApiError(409, 'Run is not awaiting review'))).toBe(
      "This run can't continue right now. It may have changed (see it below), or another post is still being written; wait for it to finish.",
    )
  })

  it('shows the general message, not the detail, for another status', () => {
    expect(resumeRunErrorMessage(new ApiError(500, 'provider timeout: upstream 503'))).toBe(
      "Couldn't continue the run. Try again.",
    )
  })

  it('shows the general message for a network failure', () => {
    expect(resumeRunErrorMessage(new TypeError('Failed to fetch'))).toBe(
      "Couldn't continue the run. Try again.",
    )
  })
})
