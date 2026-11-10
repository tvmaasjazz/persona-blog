import { useMutation } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { components } from '@/lib/api-schema.gen'

export type RecordContentItemViewVariables = {
  contentItemIdentity: string
  readPercent: components['schemas']['RecordContentItemViewDto']['read_percent']
}

// A failed view is dropped: nothing is thrown, toasted or retried.
async function recordContentItemView({
  contentItemIdentity,
  readPercent,
}: RecordContentItemViewVariables) {
  await apiClient.PUT('/content-items/{content_item_identity}/view', {
    params: { path: { content_item_identity: contentItemIdentity } },
    body: { read_percent: readPercent },
  })
}

export function useRecordContentItemView() {
  return useMutation({ mutationFn: recordContentItemView })
}
