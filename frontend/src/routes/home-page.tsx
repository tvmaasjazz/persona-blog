import { ListSearchBox } from '@/components/list-search-box'
import { PublicBlogPostFeed } from '@/features/blog-posts/components/public-blog-post-feed'
import { useListSearchParams } from '@/lib/use-list-search-params'

export function HomePage() {
  // The search lives in the URL; the feed has one order
  const { search, setSearch } = useListSearchParams()

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
