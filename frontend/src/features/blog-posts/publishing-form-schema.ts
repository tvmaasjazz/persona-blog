import { z } from 'zod'

import type { components } from '@/lib/api-schema.gen'

type BlogPostResponseDto = components['schemas']['BlogPostResponseDto']

export type PublishMode = 'draft' | 'now' | 'schedule'

export type PublishStatus = 'DRAFT' | 'SCHEDULED' | 'PUBLISHED'

// A datetime-local input's value is local time without an offset: YYYY-MM-DDTHH:mm.
function parseLocalDateTime(localDateTime: string): Date | null {
  const parsed = new Date(localDateTime)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function toLocalDateTime(date: Date): string {
  const pad = (part: number) => String(part).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

// Validates the publishing controls shared by the save-from-run and edit-post forms. The
// parent forms nest these values under a `publishing` key.
export const publishingFormSchema = z
  .object({
    isPublic: z.boolean(),
    publishMode: z.enum(['draft', 'now', 'schedule']),
    scheduledAt: z.string(),
  })
  .superRefine((values, context) => {
    if (values.publishMode !== 'schedule') {
      return
    }
    const scheduledDate = parseLocalDateTime(values.scheduledAt)
    if (!scheduledDate) {
      context.addIssue({
        code: 'custom',
        path: ['scheduledAt'],
        message: 'Pick a date and time to publish',
      })
    } else if (scheduledDate.getTime() <= Date.now()) {
      context.addIssue({
        code: 'custom',
        path: ['scheduledAt'],
        message: 'Pick a time in the future',
      })
    }
  })

export type PublishingFormValues = z.input<typeof publishingFormSchema>

export const EMPTY_PUBLISHING_VALUES: PublishingFormValues = {
  isPublic: false,
  publishMode: 'draft',
  scheduledAt: '',
}

// The published_at to send. Publish now keeps an existing past date, so saving an edit
// to a published post doesn't move it. The offset is always included: the backend
// rejects a naive datetime.
export function toPublishedAt(values: PublishingFormValues): string | null {
  if (values.publishMode === 'draft') {
    return null
  }
  const now = new Date()
  const scheduledDate = parseLocalDateTime(values.scheduledAt)
  if (values.publishMode === 'now') {
    return (scheduledDate && scheduledDate <= now ? scheduledDate : now).toISOString()
  }
  return scheduledDate ? scheduledDate.toISOString() : now.toISOString()
}

export function findPublishStatus(publishedAt: string | null): PublishStatus {
  if (publishedAt === null) {
    return 'DRAFT'
  }
  return new Date(publishedAt).getTime() > Date.now() ? 'SCHEDULED' : 'PUBLISHED'
}

export function publishingValuesFromPost({
  is_public,
  published_at,
}: Pick<BlogPostResponseDto, 'is_public' | 'published_at'>): PublishingFormValues {
  const status = findPublishStatus(published_at ?? null)
  if (!published_at || status === 'DRAFT') {
    return { ...EMPTY_PUBLISHING_VALUES, isPublic: is_public }
  }
  return {
    isPublic: is_public,
    publishMode: status === 'SCHEDULED' ? 'schedule' : 'now',
    scheduledAt: toLocalDateTime(new Date(published_at)),
  }
}
