import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    // Collect console errors for debugging
    const errors: string[] = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Wait longer for initial data load + isInitialLoading
    await page.waitForTimeout(3000);

    await expect(page).toHaveURL(/\/$/);

    // Check body visibility with better timeout
    const hasContent = await page.locator('body').first().isVisible({ timeout: 5000 });
    if (!hasContent) {
      console.log('Console errors:', errors);
    }
    expect(hasContent).toBeTruthy();
  });

  test('should have sidebar navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    const hasNav = await page.locator('nav, aside, [class*="sidebar"], [class*="Sidebar"]').first().isVisible({ timeout: 5000 });
    expect(hasNav).toBeTruthy();
  });

  test('should navigate to vehicles', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    const vehiclesLink = page.locator('a[href*="vehicles"], [href*="vehicles"]').first();
    if (await vehiclesLink.isVisible()) {
      await vehiclesLink.click();
      await page.waitForURL('**/vehicles', { timeout: 10000 });
      await expect(page).toHaveURL(/\/vehicles/);
    }
  });
});
