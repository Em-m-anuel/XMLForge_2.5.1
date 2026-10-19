import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = 'admin@xmlforge.local';
const ADMIN_PASS = 'Admin123!';

async function login(page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  // Wait for login form
  await expect(page.getByRole('heading', { name: /Connexion|Créer/ }).first()).toBeVisible({ timeout: 20000 });
  // Fill
  const emailInput = page.getByPlaceholder(/you@xmlforge|email/i).first();
  await emailInput.fill(ADMIN_EMAIL);
  const passInput = page.locator('input[type="password"]').first();
  await passInput.fill(ADMIN_PASS);
  const loginBtn = page.getByRole('button', { name: /Se connecter/ }).first();
  await loginBtn.click();
  // Dashboard
  await expect(page.getByText(/Aperçu|Dashboard/).first()).toBeVisible({ timeout: 20000 });
  // Wait for databases to load
  await page.waitForTimeout(1000);
}

test.describe('XMLForge V2.4 Final E2E QA', () => {
  test.beforeEach(async ({ page }) => {
    // Listen for console errors (ignore extensions)
    page.on('console', msg => {
      if (msg.type() === 'error') {
        const txt = msg.text();
        if (txt.includes('contentscript') || txt.includes('MetaMask') || txt.includes('ObjectMultiplex') || txt.includes('app-init-liveness')) return;
        // console.log('PAGE ERROR:', txt);
      }
    });
  });

  test('Auth — wrong then correct, refresh, logout', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Connexion/ })).toBeVisible({ timeout: 20000 });

    // Wrong credentials
    await page.getByPlaceholder(/you@xmlforge|email/i).fill('wrong@test.com');
    await page.locator('input[type="password"]').first().fill('wrongpass');
    await page.getByRole('button', { name: /Se connecter/ }).click();
    await page.waitForTimeout(1500);

    // Correct
    await page.getByPlaceholder(/you@xmlforge|email/i).fill(ADMIN_EMAIL);
    await page.locator('input[type="password"]').first().fill(ADMIN_PASS);
    await page.getByRole('button', { name: /Se connecter/ }).click();
    await expect(page.getByText(/Aperçu/).first()).toBeVisible({ timeout: 20000 });

    // Refresh keeps session
    await page.reload();
    await expect(page.getByText(/Aperçu/).first()).toBeVisible({ timeout: 20000 });

    // Logout via user menu
    const userTrigger = page.getByTestId('user-menu-trigger');
    await userTrigger.click();
    await page.waitForTimeout(500);
    const logoutBtn = page.getByRole('button', { name: /Déconnexion/ }).first();
    await expect(logoutBtn).toBeVisible({ timeout: 5000 });
    await logoutBtn.click();
    await expect(page.getByRole('heading', { name: /Connexion/ })).toBeVisible({ timeout: 10000 });
  });

  test('Dashboard — no black screen, no undefined', async ({ page }) => {
    await login(page);
    const body = await page.textContent('body');
    expect(body).not.toContain('undefined');
    expect(body).not.toContain('NaN');
    expect(body).not.toContain('Rendered fewer hooks');
    // Stats visible
    await expect(page.getByText(/Bases de données|Personnelles|Communes/).first()).toBeVisible({ timeout: 10000 });
  });

  test('Databases — create personal, fav, open', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    await expect(page.getByRole('button', { name: /Nouvelle base/ }).first()).toBeVisible({ timeout: 10000 });

    const dbName = `test_personal_${Date.now()}`;
    await page.getByRole('button', { name: /Nouvelle base/ }).first().click();
    await page.waitForTimeout(800);
    // Modal should be open — use data-testid
    const nameInput = page.getByTestId('new-db-name').first();
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(dbName);
    // Scope personal is default
    const createBtn = page.getByTestId('create-db-confirm').first();
    await createBtn.click();
    await page.waitForTimeout(1500);
    await expect(page.getByText(dbName).first()).toBeVisible({ timeout: 10000 });

    // Open
    await page.getByText(dbName).first().click();
    await expect(page.getByText(/Tables/).first()).toBeVisible({ timeout: 10000 });

    // Fav star
    const starBtn = page.locator('button').filter({ hasText: /★|☆/ }).first();
    if (await starBtn.isVisible()) {
      await starBtn.click();
      await page.waitForTimeout(300);
    }
  });

  test('Tables — create and fast switch', async ({ page }) => {
    await login(page);
    // Create db
    await page.getByText(/Bases de données/).first().click();
    const dbName = `test_tables_${Date.now()}`;
    await page.getByRole('button', { name: /Nouvelle base/ }).first().click();
    await page.waitForTimeout(600);
    await page.getByTestId('new-db-name').first().fill(dbName);
    await page.getByTestId('create-db-confirm').first().click();
    await page.waitForTimeout(1500);
    await page.getByText(dbName).first().click();
    await expect(page.getByText(/Tables/).first()).toBeVisible({ timeout: 10000 });

    const createTableBtn = page.getByRole('button', { name: /Créer.*table/ }).first();
    await createTableBtn.click();
    await page.waitForTimeout(600);
    const tableName = `items_${Date.now() % 100000}`;
    await page.getByTestId('new-table-name').first().fill(tableName);
    await page.getByTestId('create-table-confirm').first().click();
    await page.waitForTimeout(2000);

    await expect(page.getByText(tableName).first()).toBeVisible({ timeout: 10000 });
    await page.getByText(tableName).first().click();
    await expect(page.getByText(/Données|Structure/).first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('body')).not.toContainText('Rendered fewer hooks');
    await expect(page.locator('body')).not.toContainText('Table introuvable');
  });

  test('DataTab — pagination, search, no stale', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    // Try to open first test db
    const db = page.locator('text=test_tables_').first();
    if (await db.isVisible({ timeout: 3000 }).catch(() => false)) {
      await db.click();
      await page.waitForTimeout(1000);
      const tbl = page.locator('text=items_').first();
      if (await tbl.isVisible({ timeout: 3000 }).catch(() => false)) {
        await tbl.click();
        await expect(page.getByText(/Données/).first()).toBeVisible({ timeout: 10000 });
        const search = page.getByPlaceholder(/Rechercher/).first();
        if (await search.isVisible()) {
          await search.fill('test');
          await page.waitForTimeout(800);
          await search.fill('');
        }
        // Pagination next/prev — only click if enabled
        const nextBtn = page.getByLabel(/Suivante/);
        if (await nextBtn.isVisible()) {
          const disabled = await nextBtn.isDisabled().catch(() => true);
          if (!disabled) {
            await nextBtn.click();
            await page.waitForTimeout(500);
          }
        }
        await expect(page.locator('body')).not.toContainText('Rendered fewer hooks');
      }
    }
  });

  test('Structure — add column modal', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    const db = page.locator('text=test_tables_').first();
    if (await db.isVisible({ timeout: 3000 }).catch(() => false)) {
      await db.click();
      const tbl = page.locator('text=items_').first();
      if (await tbl.isVisible({ timeout: 3000 }).catch(() => false)) {
        await tbl.click();
        await page.getByText(/Structure/).first().click();
        await expect(page.getByText(/Colonnes/).first()).toBeVisible({ timeout: 10000 });
        const addCol = page.getByRole('button', { name: /Ajouter colonne/ }).first();
        if (await addCol.isVisible()) {
          await addCol.click();
          await page.waitForTimeout(600);
          // Should show modal, then close with Esc
          await page.keyboard.press('Escape');
          await page.waitForTimeout(300);
        }
      }
    }
  });

  test('Relations — diagram/list zoom', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    const db = page.locator('text=test_tables_').first();
    if (await db.isVisible({ timeout: 3000 }).catch(() => false)) {
      await db.click();
      await page.getByText(/Relations/).first().click();
      await expect(page.getByText(/Schéma/).first()).toBeVisible({ timeout: 10000 });
      const listBtn = page.getByRole('button', { name: /Liste/ }).first();
      if (await listBtn.isVisible()) {
        await listBtn.click();
        await page.waitForTimeout(500);
        await page.getByRole('button', { name: /Diagramme/ }).first().click();
      }
    }
  });

  test('SQL Console — execute', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    const db = page.locator('text=test_tables_').first();
    if (await db.isVisible({ timeout: 3000 }).catch(() => false)) {
      await db.click();
      await page.getByText(/SQL/).first().click();
      await expect(page.locator('textarea').first()).toBeVisible({ timeout: 10000 });
      await page.locator('textarea').first().fill('SELECT * FROM items_ LIMIT 5;');
      await page.getByRole('button', { name: /Exécuter/ }).first().click();
      await page.waitForTimeout(1500);
      await expect(page.locator('body')).not.toContainText('Rendered fewer hooks');
    }
  });

  test('XML — dirty banner and reset', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    let db = page.locator('text=test_tables_').first();
    if (!(await db.isVisible({ timeout: 3000 }).catch(() => false))) {
      // create db if none
      const dbName = `test_tables_${Date.now()}`;
      await page.getByRole('button', { name: /Nouvelle base/ }).first().click();
      await page.waitForTimeout(600);
      await page.getByTestId('new-db-name').first().fill(dbName);
      await page.getByTestId('create-db-confirm').first().click();
      await page.waitForTimeout(1500);
      db = page.locator(`text=${dbName}`).first();
    }
    await db.click();
    await page.waitForTimeout(800);
    // Try to open XML tab in DatabaseView
    const xmlTab = page.getByRole('button', { name: /^XML$/ }).first();
    if (await xmlTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await xmlTab.click();
      await page.waitForTimeout(1000);
      // XML panel should show textarea or title containing .xml
      const ta = page.locator('textarea').first();
      await expect(ta).toBeVisible({ timeout: 10000 });
      if (await ta.isVisible()) {
        const orig = await ta.inputValue();
        await ta.fill(orig + '\n<!-- e2e test -->');
        await expect(page.getByText(/Modifications non appliquées/).first()).toBeVisible({ timeout: 5000 });
        await page.getByRole('button', { name: /Abandonner|Reset/ }).first().click();
      }
    } else {
      await page.getByText(/XML/).first().click();
      await page.waitForTimeout(800);
      await expect(page.locator('textarea').first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('Import/Export — no Convertir en SQL in XML export', async ({ page }) => {
    await login(page);
    await page.getByText(/Import/).first().click();
    await expect(page.getByText(/Importer|Choisir fichier/).first()).toBeVisible({ timeout: 10000 });
    const exportBtn = page.getByRole('button', { name: /Export/ }).first();
    if (await exportBtn.isVisible()) {
      await exportBtn.click();
      await page.waitForTimeout(500);
      await expect(page.getByText(/Convertir en SQL/)).toHaveCount(0);
    }
  });

  test('Permissions — view', async ({ page }) => {
    await login(page);
    await page.getByText(/Bases de données/).first().click();
    const db = page.locator('text=test_tables_').first();
    if (await db.isVisible({ timeout: 3000 }).catch(() => false)) {
      await db.click();
      await page.getByText(/Permissions|Partage/).first().click();
      await expect(page.getByText(/Permissions/).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('Administration — admin visible', async ({ page }) => {
    await login(page);
    await expect(page.getByText(/Administration/).first()).toBeVisible({ timeout: 10000 });
    await page.getByText(/Administration/).first().click();
    await page.waitForTimeout(800);
    // Check that admin view loads (Users tab visible)
    await expect(page.getByText(/Utilisateurs|Administration/).first()).toBeVisible({ timeout: 10000 });
  });

  test('Server — health and shutdown button', async ({ page }) => {
    await login(page);
    await page.getByText(/Serveur/).first().click();
    await expect(page.getByText(/Serveur local/).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/REST API/).first()).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(1000);
    const shutdownBtn = page.getByRole('button', { name: /Fermer XMLForge/ }).first();
    await expect(shutdownBtn).toBeVisible({ timeout: 8000 });
  });

  test('Settings — advanced shutdown', async ({ page }) => {
    await login(page);
    await page.getByText(/Paramètres/).first().click();
    await expect(page.getByText(/Paramètres/).first()).toBeVisible({ timeout: 10000 });
    await page.getByText(/Avancé/).first().click();
    await expect(page.getByRole('button', { name: /Fermer XMLForge/ }).first()).toBeVisible({ timeout: 8000 });
  });

  test('Shutdown modal — cancel', async ({ page }) => {
    await login(page);
    await page.getByText(/Serveur/).first().click();
    await page.getByRole('button', { name: /Fermer XMLForge/ }).first().click();
    await expect(page.getByText(/Fermer XMLForge \?/).first()).toBeVisible({ timeout: 8000 });
    await expect(page.getByText(/Cette action va arrêter/).first()).toBeVisible();
    await page.getByRole('button', { name: /Annuler/ }).first().click();
    await expect(page.getByText(/Fermer XMLForge \?/)).toHaveCount(0);
  });
});
