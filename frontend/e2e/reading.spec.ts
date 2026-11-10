import { expect, test } from './fixtures.ts'

test('a signed-out reader searches the feed, and a search with no match says so', async ({
  page,
}) => {
  await page.goto('/')
  const searchBox = page.getByRole('searchbox', { name: 'Search posts' })
  const postLinks = page.getByRole('heading', { level: 2 }).getByRole('link')

  // A seeded title narrows the feed to posts with it
  await searchBox.fill('Old Maps')
  await expect(postLinks.first()).toContainText('Old Maps')
  await expect(page.getByText("That's every match.")).toBeVisible()
  for (const postLink of await postLinks.all()) {
    await expect(postLink).toContainText('Old Maps')
  }

  // A term nothing contains shows the no-match message and no posts
  await searchBox.fill('zzqxjvk')
  await expect(page.getByText('No posts match "zzqxjvk".')).toBeVisible()
  await expect(postLinks).toHaveCount(0)
})

test('a signed-out reader reads a post and finds its persona with their posts', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('searchbox', { name: 'Search posts' }).fill('Old Maps, Entry 7')
  await page.getByRole('link', { name: 'Old Maps, Entry 7', exact: true }).click()

  // The post shows its title and body, with no owner actions
  await expect(page.getByRole('heading', { level: 1, name: 'Old Maps, Entry 7' })).toBeVisible()
  await expect(page.getByText('This is entry 7, and it is about old maps.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Edit' })).toHaveCount(0)

  // Its persona's page shows the bio and her posts
  await page.getByRole('link', { name: 'Ada Quill' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ada Quill' })).toBeVisible()
  await expect(
    page.getByText('A home baker who writes plainly about bread and the patience it asks for.'),
  ).toBeVisible()
  await expect(page.getByRole('heading', { level: 2 }).getByRole('link').first()).toBeVisible()
  // Only her posts are listed: a post by Bram Holt is not
  await expect(page.getByRole('link', { name: /Slow Mornings, Entry/ })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Edit' })).toHaveCount(0)
})

test('a private persona is not found by a signed-out visitor or a reader', async ({
  page,
  context,
  signInAs,
}) => {
  // The owner finds the private persona's id in their own list
  await signInAs('creator')
  await page.goto('/personas')
  const cassLink = page.getByRole('link', { name: /Cass Mire/ })
  await expect(cassLink).toBeVisible()
  const cassPath = await cassLink.getAttribute('href')
  if (cassPath === null || !/^\/personas\/[\w-]+$/.test(cassPath)) {
    throw new Error(`Cass Mire's link has no persona path: ${cassPath}`)
  }

  // Signed out
  await context.clearCookies()
  await page.goto(cassPath)
  await expect(page.getByText('Persona not found.')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1, name: 'Cass Mire' })).toHaveCount(0)

  // A reader, who is signed in but not the owner
  await signInAs('reader')
  await page.goto(cassPath)
  await expect(page.getByText('Persona not found.')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1, name: 'Cass Mire' })).toHaveCount(0)
})

test("a private persona's public post stays out of the feed", async ({ page }) => {
  await page.goto('/')
  await page.getByRole('searchbox', { name: 'Search posts' }).fill('Bread and Patience, Entry 301')
  await expect(page.getByText('No posts match "Bread and Patience, Entry 301".')).toBeVisible()
  await expect(page.getByRole('link', { name: /Entry 301/ })).toHaveCount(0)
})

test('a reader is told they have no access to write', async ({ page, signInAs }) => {
  await signInAs('reader')
  await page.goto('/write')
  await expect(page.getByRole('heading', { level: 1, name: 'No access' })).toBeVisible()
  await expect(
    page.getByText(
      'Your account can read posts. Creating personas and posts is by invitation for now.',
    ),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Write a post' })).toHaveCount(0)
})
