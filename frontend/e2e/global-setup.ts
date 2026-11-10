import type { components } from '../src/lib/api-schema.gen.ts'

type PublicBlogPostPageResponseDto = components['schemas']['PublicBlogPostPageResponseDto']

// The flows run only against a local development API on port 8000 with the dev seed in
// it, which is where Vite's /api proxy points; anything else stops the run before a test
// starts. Signed-in flows are also refused outside local development by dev_session.
const LOCAL_API_URL = 'http://localhost:8000'
const SEEDED_POST_TITLE = 'Bread and Patience, Entry 1'

export default async function globalSetup() {
  // The API is up, and it's a development API
  let healthResponse: Response
  try {
    healthResponse = await fetch(`${LOCAL_API_URL}/health`)
  } catch {
    throw new Error(
      `No API at ${LOCAL_API_URL}. Start it from backend/: uv run granian --interface asgi apps.api.main:app`,
    )
  }
  if (!healthResponse.ok) {
    throw new Error(`The API at ${LOCAL_API_URL} answered ${healthResponse.status} to /health`)
  }
  const health = (await healthResponse.json()) as { environment?: string }
  if (health.environment !== 'DEVELOPMENT') {
    throw new Error(`The API at ${LOCAL_API_URL} is ${health.environment}, not DEVELOPMENT`)
  }

  // The dev seed is in it: one of Ada Quill's seeded posts is public
  const feedResponse = await fetch(
    `${LOCAL_API_URL}/blog-posts/public?search=${encodeURIComponent(SEEDED_POST_TITLE)}`,
  )
  if (!feedResponse.ok) {
    throw new Error(`The API answered ${feedResponse.status} to the public feed`)
  }
  const feed = (await feedResponse.json()) as PublicBlogPostPageResponseDto
  if (!feed.blog_posts.some((blogPost) => blogPost.title === SEEDED_POST_TITLE)) {
    throw new Error('The dev seed is missing. From backend/: uv run python -m scripts.dev_seed')
  }
}
