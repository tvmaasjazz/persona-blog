import { useSearchParams } from 'react-router'

import { WriteBlogPost } from '@/features/generate-text/components/write-blog-post'
import { usePersonaList } from '@/features/personas/api/persona-list-query'
import { apiErrorMessage } from '@/lib/api-error'

export function WritePage() {
  // Load the personas to write as
  const [searchParams] = useSearchParams()
  const { data, isPending, error } = usePersonaList()

  // Loading, error, or the write form
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-extrabold">Write a post</h1>
      {isPending ? (
        <div className="h-40 rounded-2xl bg-accent" />
      ) : error ? (
        <p className="text-muted-foreground">{apiErrorMessage(error)}</p>
      ) : (
        <WriteBlogPost
          personas={data.personas}
          preselectedPersonaIdentity={searchParams.get('persona')}
          fromRunIdentity={searchParams.get('from_run')}
        />
      )}
    </div>
  )
}
