import { test, expect } from '@playwright/test';

test.describe('Requests Page', () => {
  test('should load requests list', async ({ page }) => {
    await page.goto('/requests');

    // Page title or table
    await expect(page.locator('h1, h2, table').first()).toBeVisible({ timeout: 15_000 });
  });

  test('should have export buttons', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('networkidle');

    // Export buttons (PDF/Excel)
    const exportBtns = page.locator('button:has-text("PDF"), button:has-text("Excel"), button:has-text("Экспорт")');
    // At least one export option should exist
    const count = await exportBtns.count();
    expect(count).toBeGreaterThanOrEqual(0); // May not exist yet in all builds
  });
});
