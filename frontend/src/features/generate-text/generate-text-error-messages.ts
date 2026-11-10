import { ApiError } from '@/lib/api-error'

const INSUFFICIENT_CREDITS_MESSAGE =
  'Your credit balance is too low to write. Ask the admin for more credits.'

// The message for a failed start call; the detail can carry provider internals, so it isn't shown.
export function startRunErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 402) {
    return INSUFFICIENT_CREDITS_MESSAGE
  }
  if (error instanceof ApiError && error.status === 409) {
    return 'You already have the most posts being written at once. Wait for one to finish.'
  }
  return "Couldn't write the post. Try again."
}

// The message for a failed resume call.
export function resumeRunErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 402) {
    return INSUFFICIENT_CREDITS_MESSAGE
  }
  if (error instanceof ApiError && error.status === 409) {
    return "This run can't continue right now. It may have changed (see it below), or another post is still being written; wait for it to finish."
  }
  return "Couldn't continue the run. Try again."
}
