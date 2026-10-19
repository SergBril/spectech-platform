import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/$/);
    const hasContent = await page.locator('h1, h2, main, [role="main"]').first().isVisible();
    expect(hasContent).toBeTruthy();
  });

  test('should have sidebar navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const hasNav = await page.locator('nav, aside, [class*="sidebar"]').first().isVisible();
    expect(hasNav).toBeTruthy();
  });

  test('should navigate to vehicles', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const vehiclesLink = page.locator('a[href="/vehicles"], button:has-text("Техника")').first();
    if (await vehiclesLink.isVisible()) {
      await vehiclesLink.click();
      await page.waitForURL('**/vehicles');
      await expect(page).toHaveURL(/\/vehicles/);
    }
  });
});
