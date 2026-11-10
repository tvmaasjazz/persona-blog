import { Badge } from '@/components/ui/badge'
import { findPublishStatus } from '@/features/blog-posts/publishing-form-schema'
import { formatDate } from '@/lib/format-date'

type PostStatusBadgesProps = {
  publishedAt: string | null | undefined
  isPublic: boolean
  isPersonaPublic: boolean
}

export function PostStatusBadges({
  publishedAt,
  isPublic,
  isPersonaPublic,
}: PostStatusBadgesProps) {
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
      <Badge variant={isPublic ? 'secondary' : 'outline'}>
        {isPublic
          ? isPersonaPublic
            ? 'Public'
            : 'Public · hidden while the persona is private'
          : 'Private'}
      </Badge>
    </div>
  )
}
