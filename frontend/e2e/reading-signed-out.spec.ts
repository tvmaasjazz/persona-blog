import { expect, test } from './fixtures.ts'

test('a signed-out reader opens a post from the feed and goes to its persona', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'From the personas' })).toBeVisible()

  // Narrow the feed to one seeded post of Ada Quill's, then open it
  const postTitle = 'Bread and Patience, Entry 1'
  await page.getByRole('searchbox', { name: 'Search posts' }).fill(postTitle)
  await page.getByRole('link', { name: postTitle, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: postTitle })).toBeVisible()

  // The post links to its persona's page (the avatar and the name are one link)
  await page.getByRole('main').getByRole('link', { name: 'Ada Quill' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ada Quill' })).toBeVisible()
})
