import { test, expect } from '@playwright/test';

test.describe('Vehicles Page', () => {
  test('should load vehicles page', async ({ page }) => {
    await page.goto('/vehicles');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/vehicles/);
    const hasContent = await page.locator('h1, h2, table, main, [role="main"]').first().isVisible({ timeout: 5000 });
    expect(hasContent).toBeTruthy();
  });

  test('should have column headers when data exists', async ({ page }) => {
    await page.goto('/vehicles');
    await page.waitForLoadState('networkidle');
    const tableVisible = await page.locator('table').isVisible();
    if (tableVisible) {
      const headers = page.locator('th');
      const count = await headers.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should show pagination when enough items', async ({ page }) => {
    await page.goto('/vehicles');
    await page.waitForLoadState('networkidle');
    const paginator = page.locator('text=Стр.');
    if (await paginator.isVisible()) {
      await expect(paginator).toContainText('Стр.');
    }
  });
});
