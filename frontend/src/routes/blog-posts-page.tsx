import { Link, useSearchParams } from 'react-router'

import { ListPager } from '@/components/list-pager'
import { ListSearchBox } from '@/components/list-search-box'
import { Button } from '@/components/ui/button'
import { useUserBlogPostPage } from '@/features/blog-posts/api/user-blog-post-page-query'
import { BlogPostList } from '@/features/blog-posts/components/blog-post-list'
import { PersonaFilter } from '@/features/blog-posts/components/persona-filter'
import { usePersonaOptions } from '@/features/personas/api/user-persona-page-query'
import type { components } from '@/lib/api-schema.gen'
import { useListSearchParams } from '@/lib/use-list-search-params'

const SORT_VALUES = [
  'CREATED_AT',
] as const satisfies readonly components['schemas']['UserBlogPostSortType'][]
const PAGE_SIZE = 20

export function BlogPostsPage() {
  // The page, search and persona filter live in the URL
  const { page, search, setPage, setSearch } = useListSearchParams({
    sortValues: SORT_VALUES,
    defaultSort: 'CREATED_AT',
    defaultDirection: 'DESC',
  })
  const [searchParams, setSearchParams] = useSearchParams()
  const personaIdentity = searchParams.get('persona') ?? undefined

  // Load the filter options and the page of posts
  const { data: personas = [] } = usePersonaOptions()
  const { data, isPending, error } = useUserBlogPostPage({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    persona_identity: personaIdentity,
    sort_by: 'CREATED_AT',
    sort_direction: 'DESC',
  })

  // A new filter starts again from page 1
  function changePersona(nextIdentity: string | undefined) {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (nextIdentity) {
          next.set('persona', nextIdentity)
        } else {
          next.delete('persona')
        }
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  // Heading, search and filter, list, pager
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-extrabold">My Posts</h1>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <ListSearchBox label="Search posts" value={search} onChange={setSearch} />
        </div>
        <PersonaFilter
          personas={personas}
          personaIdentity={personaIdentity}
          onChange={changePersona}
        />
      </div>
      <BlogPostList
        blogPosts={data?.blog_posts}
        isPending={isPending}
        error={error}
        isNarrowed={search !== '' || personaIdentity !== undefined}
        emptyState={
          <div className="flex flex-col items-start gap-4 rounded-2xl border bg-card p-6">
            <p className="text-muted-foreground">No posts yet. Write your first one.</p>
            <Button asChild>
              <Link to="/write">Write a post</Link>
            </Button>
          </div>
        }
      />
      {data && <ListPager pagination={data.pagination} onPageChange={setPage} />}
    </div>
  )
}
