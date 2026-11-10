import { useMutation } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import { createApiError } from '@/lib/api-error'
import type { components } from '@/lib/api-schema.gen'

export type RecordContentItemViewVariables = {
  contentItemIdentity: string
  readPercent: components['schemas']['RecordContentItemViewDto']['read_percent']
}

async function recordContentItemView({
  contentItemIdentity,
  readPercent,
}: RecordContentItemViewVariables) {
  const { error, response } = await apiClient.PUT('/content-items/{content_item_identity}/view', {
    params: { path: { content_item_identity: contentItemIdentity } },
    body: { read_percent: readPercent },
  })
  if (error) {
    throw createApiError(error, response)
  }
}

export function useRecordContentItemView() {
  return useMutation({ mutationFn: recordContentItemView })
}
