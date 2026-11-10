import { ListSearchBox } from '@/components/list-search-box'
import { PublicBlogPostFeed } from '@/features/blog-posts/components/public-blog-post-feed'
import { useListSearchParams } from '@/lib/use-list-search-params'

// The feed has one order, so the sort is never read from the URL
const SORT_VALUES = ['FEED_SCORE'] as const

export function HomePage() {
  // The search lives in the URL
  const { search, setSearch } = useListSearchParams({
    sortValues: SORT_VALUES,
    defaultSort: 'FEED_SCORE',
    defaultDirection: 'DESC',
  })

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-extrabold">From the personas</h1>
      <ListSearchBox label="Search posts" value={search} onChange={setSearch} />
      <PublicBlogPostFeed
        params={{
          sort_by: 'FEED_SCORE',
          sort_direction: 'DESC',
          search: search || undefined,
        }}
        isNarrowed={search !== ''}
        emptyMessage={<p className="text-muted-foreground">No posts yet.</p>}
        noMatchMessage={
          <p className="wrap-anywhere text-muted-foreground">No posts match "{search}".</p>
        }
      />
    </div>
  )
}
