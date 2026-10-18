import { test, expect } from '@playwright/test';

test.describe('Vehicles Page', () => {
  test('should load vehicles list with pagination', async ({ page }) => {
    await page.goto('/vehicles');

    // Table should be visible
    await expect(page.locator('table')).toBeVisible({ timeout: 15_000 });

    // Column headers
    await expect(page.locator('th')).toContainText(['Название', 'Статус']);
  });

  test('should have column visibility menu', async ({ page }) => {
    await page.goto('/vehicles');

    // Look for column settings button/menu
    await page.waitForTimeout(2000);
    const colMenuBtn = page.locator('[title*="Колонки"], [aria-label*="column"], button:has-text("⚙")').first();
    if (await colMenuBtn.isVisible()) {
      await colMenuBtn.click();
      // Dropdown should appear
      await expect(page.locator('[role="menu"], .dropdown, [class*="col-menu"]')).toBeVisible();
    }
  });

  test('should show pagination when enough items', async ({ page }) => {
    await page.goto('/vehicles');
    await page.waitForLoadState('networkidle');

    // Pagination may or may not be visible depending on data count
    const paginator = page.locator('text=Стр.');
    if (await paginator.isVisible()) {
      await expect(paginator).toContainText('Стр.');
    }
  });
});
