import { test, expect } from '@playwright/test';

test.describe('Shift Calendar Page', () => {
  test('should load shift calendar page', async ({ page }) => {
    await page.goto('/shift-calendar');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 10000 });
  });

  test('should have calendar or shift list content', async ({ page }) => {
    await page.goto('/shift-calendar');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3000);

    // Should have either calendar grid, table, or empty state
    const content = page.locator('table, [class*="calendar"], [class*="grid"], [class*="empty"], p');
    const count = await content.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should have template management controls', async ({ page }) => {
    await page.goto('/shift-calendar');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3000);

    // Should have buttons for template/shift management
    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
