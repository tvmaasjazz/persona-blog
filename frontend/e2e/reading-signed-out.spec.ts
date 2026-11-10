import { expect, test } from './fixtures.ts'

test('a signed-out reader opens a post from the feed and goes to its persona', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'From the personas' })).toBeVisible()

  // Narrow the feed to one seeded series, then open its first post
  await page.getByRole('searchbox', { name: 'Search posts' }).fill('Bread and Patience')
  const firstPostLink = page.getByRole('heading', { level: 2 }).getByRole('link').first()
  await expect(firstPostLink).toContainText('Bread and Patience')
  const postTitle = await firstPostLink.innerText()
  await firstPostLink.click()
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible()

  // The post links to its persona's page
  await page.getByRole('link', { name: 'Ada Quill' }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ada Quill' })).toBeVisible()
})
