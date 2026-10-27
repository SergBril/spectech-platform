import { test, expect } from '@playwright/test';

test.describe('Driver KPI Page', () => {
  test('should load driver KPI page', async ({ page }) => {
    await page.goto('/driver-kpi');
    await page.waitForLoadState('domcontentloaded');
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 10000 });
  });

  test('should have date filters and export button', async ({ page }) => {
    await page.goto('/driver-kpi');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Date inputs
    const dateInputs = page.locator('input[type="date"]');
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);

    // Export button
    const exportBtn = page.locator('button:has-text("Экспорт")');
    await expect(exportBtn).toBeVisible({ timeout: 5000 });
  });

  test('should show table or empty state', async ({ page }) => {
    await page.goto('/driver-kpi');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);

    // Either table with data or empty state message
    const table = page.locator('table');
    const emptyState = page.locator('text=Нет данных');
    const hasTable = await table.isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);

    expect(hasTable || hasEmpty).toBeTruthy();
  });
});
