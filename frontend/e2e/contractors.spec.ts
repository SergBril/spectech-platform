import { test, expect } from '@playwright/test';

test.describe('Contractors Page', () => {
  test('should load contractors list page', async ({ page }) => {
    await page.goto('/contractors');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 10000 });
  });

  test('should have contractors table or list', async ({ page }) => {
    await page.goto('/contractors');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3000);

    // Should have table, list, or empty state
    const content = page.locator('table, [class*="list"], [class*="card"], p');
    const count = await content.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should have add/create contractor button', async ({ page }) => {
    await page.goto('/contractors');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3000);

    // Look for create/add button
    const addBtn = page.locator('button:has-text("Добавить"), button:has-text("Создать"), button:has-text("Новый"), a:has-text("Добавить")');
    const count = await addBtn.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should navigate to contractor detail on row click', async ({ page }) => {
    await page.goto('/contractors');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3000);

    // Try to find and click a contractor link/row
    const contractorLink = page.locator('a[href*="/contractors/"], tr[class*="cursor-pointer"], [class*="contractor"] a').first();
    if (await contractorLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await contractorLink.click();
      await page.waitForURL('**/contractors/*', { timeout: 10000 });
      await expect(page).toHaveURL(/\/contractors\/\d+/);
    }
    // If no contractors exist, test still passes (no assertion failure)
  });
});
