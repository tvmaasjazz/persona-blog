import { expect, test } from './fixtures.ts'

test('the creator lists their personas and searches them', async ({ page, signInAs }) => {
  await signInAs('creator')
  await page.goto('/personas')
  await expect(page.getByRole('heading', { level: 1, name: 'My Personas' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Ada Quill/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Bram Holt/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Cass Mire/ })).toContainText('Private')

  // A search narrows the list to the match
  await page.getByRole('searchbox', { name: 'Search personas' }).fill('Bram')
  await expect(page.getByRole('link', { name: /Bram Holt/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Ada Quill/ })).toHaveCount(0)
  await expect(page).toHaveURL(/q=Bram/)

  // A search with no match says so
  await page.getByRole('searchbox', { name: 'Search personas' }).fill('zzqxjvk')
  await expect(page.getByText('No personas match your search.')).toBeVisible()
})

test('the creator pages through their posts and searches them', async ({ page, signInAs }) => {
  await signInAs('creator')
  await page.goto('/posts')
  await expect(page.getByRole('heading', { level: 1, name: 'My Posts' })).toBeVisible()
  await expect(page.getByText(/^Page 1 of \d+$/)).toBeVisible()

  // The pager moves to page 2, and the URL follows
  await page.getByRole('button', { name: 'Next' }).click()
  await expect(page.getByText(/^Page 2 of \d+$/)).toBeVisible()
  await expect(page).toHaveURL(/page=2/)

  // A search returns to page 1 with only the matching posts
  const searchBox = page.getByRole('searchbox', { name: 'Search posts' })
  await searchBox.fill('Bread and Patience')
  await expect(page).not.toHaveURL(/page=2/)
  const postLinks = page.getByRole('link', { name: /Bread and Patience, Entry/ })
  await expect(postLinks.first()).toBeVisible()
  await expect(page.getByRole('link', { name: /Slow Mornings, Entry/ })).toHaveCount(0)

  // A search with no match says so
  await searchBox.fill('zzqxjvk')
  await expect(page.getByText('No posts match your search or filter.')).toBeVisible()
})

test('making a public persona private asks first, and cancelling saves nothing', async ({
  page,
  signInAs,
}) => {
  await signInAs('creator')
  await page.goto('/personas')
  const bramPath = await page.getByRole('link', { name: /Bram Holt/ }).getAttribute('href')
  const bramIdentity = bramPath?.split('/').pop()

  // Read how many public posts Bram has from the same route the edit page counts with
  const countResponse = await page.request.get(
    `/api/blog-posts/public?persona_identity=${bramIdentity}&page_size=1`,
  )
  expect(countResponse.ok()).toBe(true)
  const publicPostCount = (await countResponse.json()).pagination.total
  expect(publicPostCount).toBeGreaterThan(1)

  await page.getByRole('link', { name: /Bram Holt/ }).click()
  await page.getByRole('link', { name: 'Edit' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Edit persona' })).toBeVisible()

  // Switching Public off and saving opens the warning, naming the persona and its posts
  const publicSwitch = page.getByRole('switch', { name: 'Public' })
  await expect(publicSwitch).toBeChecked()
  await publicSwitch.click()
  await page.getByRole('button', { name: 'Save changes' }).click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog.getByRole('heading', { name: 'Make Bram Holt private?' })).toBeVisible()
  await expect(dialog).toContainText(
    `Its ${publicPostCount} public posts will be hidden until the persona is public again.`,
  )

  // Cancelling closes the dialog without saving
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('Persona saved')).toHaveCount(0)
  await page.goto('/personas')
  await expect(page.getByRole('link', { name: /Bram Holt/ })).toContainText('Public')
  await expect(page.getByRole('link', { name: /Bram Holt/ })).not.toContainText('Private')
})

test('a creator with no credits is told so when they try to write', async ({ page, signInAs }) => {
  await signInAs('brokeCreator')
  await page.goto('/write')
  await expect(page.getByRole('heading', { level: 1, name: 'Write a post' })).toBeVisible()

  // Fill the form for the broke creator's persona
  await page.getByRole('combobox', { name: 'Persona' }).click()
  await page.getByRole('option', { name: 'Milo Penny' }).click()
  await page.getByLabel('Prompt').fill('Five ways to stretch a dollar.')

  // The API refuses with a 402 before any model call, and the form stays
  await page.getByRole('button', { name: 'Write post' }).click()
  await expect(
    page.getByText('Your credit balance is too low to write. Ask the admin for more credits.'),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/write$/)
  await expect(page.getByLabel('Prompt')).toHaveValue('Five ways to stretch a dollar.')
})
