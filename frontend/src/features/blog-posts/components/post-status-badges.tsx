import { Badge } from '@/components/ui/badge'
import { findPublishStatus } from '@/features/blog-posts/publishing-form-schema'

type PostStatusBadgesProps = {
  publishedAt: string | null | undefined
  isPublic: boolean
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function PostStatusBadges({ publishedAt, isPublic }: PostStatusBadgesProps) {
  const status = findPublishStatus(publishedAt ?? null)

  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === 'DRAFT' && <Badge variant="outline">Draft</Badge>}
      {status === 'SCHEDULED' && publishedAt && (
        <Badge variant="secondary">Scheduled {formatDate(publishedAt)}</Badge>
      )}
      {status === 'PUBLISHED' && publishedAt && (
        <Badge variant="default">Published {formatDate(publishedAt)}</Badge>
      )}
      <Badge variant={isPublic ? 'secondary' : 'outline'}>{isPublic ? 'Public' : 'Private'}</Badge>
    </div>
  )
}
