import type { InfiniteData } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import type { components } from '@/lib/api-schema.gen'

import { flattenPages } from './public-blog-post-page-infinite-query'

type BlogPostSummaryResponseDto = components['schemas']['BlogPostSummaryResponseDto']
type PublicBlogPostPageResponseDto = components['schemas']['PublicBlogPostPageResponseDto']

const PAGE_SIZE = 2

function buildBlogPostSummary(identity: string, title: string): BlogPostSummaryResponseDto {
  return {
    identity,
    content_item_identity: `content-${identity}`,
    persona_identity: 'persona-1',
    persona_name: 'Ada',
    persona_avatar_url: null,
    is_persona_public: true,
    title,
    subtitle: null,
    is_public: true,
    published_at: '2026-11-01T00:00:00Z',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  }
}

// Builds infinite data whose pages hold the given posts, numbered from 1
function buildInfiniteData(
  pagesOfBlogPosts: BlogPostSummaryResponseDto[][],
): InfiniteData<PublicBlogPostPageResponseDto, number> {
  const pageNumbers = pagesOfBlogPosts.map((_, index) => index + 1)
  return {
    pages: pagesOfBlogPosts.map((blogPosts, index) => ({
      pagination: { page: index + 1, page_size: PAGE_SIZE, total: 4 },
      blog_posts: blogPosts,
    })),
    pageParams: pageNumbers,
  }
}

const firstPost = buildBlogPostSummary('post-1', 'First')
const secondPost = buildBlogPostSummary('post-2', 'Second')
const thirdPost = buildBlogPostSummary('post-3', 'Third')
const fourthPost = buildBlogPostSummary('post-4', 'Fourth')

describe('flattenPages', () => {
  it('returns the posts of a single page in order', () => {
    const infiniteData = buildInfiniteData([[firstPost, secondPost]])

    expect(flattenPages(infiniteData)).toEqual([firstPost, secondPost])
  })

  it('joins pages with no overlap in page order', () => {
    const infiniteData = buildInfiniteData([
      [firstPost, secondPost],
      [thirdPost, fourthPost],
    ])

    expect(flattenPages(infiniteData)).toEqual([firstPost, secondPost, thirdPost, fourthPost])
  })

  it('keeps the first copy of a post that appears on two pages, where it first appeared', () => {
    // The second post moved down a page, so it shows again at the top of page 2
    const movedSecondPost = { ...secondPost, title: 'Second, read again' }
    const infiniteData = buildInfiniteData([
      [firstPost, secondPost],
      [movedSecondPost, thirdPost],
    ])

    expect(flattenPages(infiniteData)).toEqual([firstPost, secondPost, thirdPost])
  })

  it('skips empty pages', () => {
    const infiniteData = buildInfiniteData([[], [firstPost], []])

    expect(flattenPages(infiniteData)).toEqual([firstPost])
  })

  it('returns no posts when every page is empty', () => {
    const infiniteData = buildInfiniteData([[], []])

    expect(flattenPages(infiniteData)).toEqual([])
  })
})
