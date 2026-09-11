import { test, expect } from '@playwright/test'

test('navigateur → React → Flask → XML avec conflit 409', async ({ page }) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  const email = `browser-${suffix}@example.com`
  const databaseName = `browser_${Date.now()}`

  await page.goto('/register')
  await page.locator('#reg-name').fill('Browser E2E')
  await page.locator('#reg-email').fill(email)
  await page.locator('#reg-pass').fill('secret123')
  await page.locator('#reg-pass2').fill('secret123')
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL(/\/login$/)

  await page.locator('#login-user').fill(email)
  await page.locator('#login-pass').fill('secret123')
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Mes bases de données' })).toBeVisible()

  await page.getByRole('button', { name: 'Nouvelle base' }).click()
  let modal = page.locator('.modal-overlay.open')
  await modal.locator('input').nth(0).fill(databaseName)
  await modal.locator('input').nth(1).fill('Base créée par le navigateur E2E')
  await modal.locator('select').selectOption('COMMON')
  await modal.getByRole('button', { name: 'Créer la base' }).click()
  await expect(page.getByRole('heading', { name: databaseName })).toBeVisible()
  const card = page.locator('.db-card').filter({ hasText: databaseName })
  await expect(card.getByText('Commune')).toBeVisible()
  await expect(card.getByText(/accès MANAGE/)).toBeVisible()
  await card.getByText('Ouvrir').click()
  await expect(page).toHaveURL(/\/database\/\d+$/)

  await page.getByRole('button', { name: 'Nouvelle table' }).click()
  modal = page.locator('.modal-overlay.open')
  await modal.locator('input').first().fill('items')
  await modal.getByRole('button', { name: 'Créer la table' }).click()
  await expect(page.locator('.ws-table-item').filter({ hasText: 'items' })).toBeVisible()

  await page.getByRole('button', { name: 'Ajouter une colonne' }).click()
  modal = page.locator('.modal-overlay.open')
  await modal.locator('input').nth(0).fill('name')
  await modal.locator('select').first().selectOption('VARCHAR')
  await modal.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.locator('.cols-table').first().getByText('name', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: /Données/ }).click()
  await page.getByRole('button', { name: /Ajouter une ligne/ }).click()
  modal = page.locator('.modal-overlay.open')
  await modal.locator('input').nth(1).fill('Nyx')
  await modal.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.locator('.tab-panel.active').getByText('Nyx', { exact: true })).toBeVisible()

  const token = await page.evaluate(() => localStorage.getItem('xmlforge_token'))
  const databaseId = Number(page.url().match(/\/database\/(\d+)/)[1])
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  const tablesResponse = await page.request.get(`/api/tables/${databaseId}`, { headers })
  const tables = (await tablesResponse.json()).data
  const tableId = tables.find(item => item.name === 'items').id
  const databaseResponse = await page.request.get(`/api/databases/${databaseId}`, { headers })
  const database = (await databaseResponse.json()).data

  await page.locator('.tab-panel.active button[title="Modifier"]').first().click()
  modal = page.locator('.modal-overlay.open')
  await modal.locator('input').nth(1).fill('Modification locale obsolète')

  const externalMutation = await page.request.post(`/api/tables/${tableId}/rows`, {
    headers,
    data: { data: { name: 'Modification externe' }, expected_version: database.document_version },
  })
  expect(externalMutation.status()).toBe(201)

  await modal.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByRole('heading', { name: 'Conflit de version' })).toBeVisible()
  await expect(page.getByText(/modifiée depuis votre dernière synchronisation/i)).toBeVisible()
  await page.getByRole('button', { name: /Recharger la version récente/i }).click()
  await expect(page.getByText('Modification externe', { exact: true })).toBeVisible()

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'API & connexions externes' })).toBeVisible()
  await expect(page.locator('.rel-section-title').filter({ hasText: /^Connexion TCP\/IP$/ })).toBeVisible()
  await expect(page.getByText('Clés API', { exact: true })).toBeVisible()
  await expect(page.getByText('Endpoints — aperçu de référence', { exact: true })).toBeVisible()

  const cleanup = await page.request.delete(`/api/databases/${databaseId}`, { headers })
  expect(cleanup.ok()).toBeTruthy()
})
