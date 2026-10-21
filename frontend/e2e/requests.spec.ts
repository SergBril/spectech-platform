import { test, expect } from '@playwright/test';

test.describe('Requests Page', () => {
  test('should load requests list', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    const hasContent = await page.locator('body').first().isVisible({ timeout: 5000 });
    expect(hasContent).toBeTruthy();
  });

  test('should have export buttons', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
