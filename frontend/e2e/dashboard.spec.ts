import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Wait for content to render
    await page.waitForTimeout(1000);
    await expect(page).toHaveURL(/\/$/);
    const hasContent = await page.locator('body').first().isVisible();
    expect(hasContent).toBeTruthy();
  });

  test('should have sidebar navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    const hasNav = await page.locator('nav, aside, [class*="sidebar"], [class*="Sidebar"]').first().isVisible();
    expect(hasNav).toBeTruthy();
  });

  test('should navigate to vehicles', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    const vehiclesLink = page.locator('a[href*="vehicles"], [href*="vehicles"]').first();
    if (await vehiclesLink.isVisible()) {
      await vehiclesLink.click();
      await page.waitForURL('**/vehicles', { timeout: 10000 });
      await expect(page).toHaveURL(/\/vehicles/);
    }
  });
});
