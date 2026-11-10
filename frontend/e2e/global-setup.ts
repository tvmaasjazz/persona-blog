// The flows run only against a local API on port 8000 with the dev seed in it, which is
// where Vite's /api proxy points; anything else stops the run before a test starts.
const LOCAL_API_URL = 'http://localhost:8000'

export default async function globalSetup() {
  // The API is up
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

  // The dev seed is in it: Ada Quill's public page is one of the seeded cases
  const feedResponse = await fetch(`${LOCAL_API_URL}/blog-posts/public?search=Bread`)
  const feed = (await feedResponse.json()) as { pagination?: { total?: number } }
  if (!feed.pagination?.total) {
    throw new Error('The dev seed is missing. From backend/: uv run python -m scripts.dev_seed')
  }
}
