export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function createApiError(error: unknown, response: Response): ApiError {
  const detail =
    typeof error === 'object' && error !== null && 'detail' in error ? error.detail : undefined

  return new ApiError(response.status, detail)
}

// True for a 401, which the API client has already announced with its signed-out toast.
export function isSessionEndedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && typeof error.detail === 'string') {
    return error.detail
  }

  return 'Something went wrong. Try again.'
}
