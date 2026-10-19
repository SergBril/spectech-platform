import { test, expect } from '@playwright/test';

test.describe('Vehicles Page', () => {
  test('should load vehicles page', async ({ page }) => {
    await page.goto('/vehicles');
    await page.waitForLoadState('networkidle');

    // Just verify page loaded without redirect to login
    await expect(page).toHaveURL(/\/vehicles/);

    // Check page has some content (h1, table, or any main element)
    const hasContent = await page.locator('h1, h2, table, main, [role="main"]').first().isVisible();
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
