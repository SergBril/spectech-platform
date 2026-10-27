import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard page', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/');
    // Deterministic wait instead of fixed timeout
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await expect(page).toHaveURL(/\/$/);

    const hasContent = await page.locator('body').first().isVisible({ timeout: 10000 });
    if (!hasContent) {
      console.log('Console errors:', errors);
    }
    expect(hasContent).toBeTruthy();
  });

  test('should have sidebar navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

    // Wait for Layout component to render sidebar with increased timeout
    const sidebar = page.locator('nav, aside, [class*="sidebar"], [class*="Sidebar"]').first();
    await expect(sidebar).toBeVisible({ timeout: 15000 });
  });

  test('should navigate to vehicles', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

    // Sidebar uses <button> with navigate(), not <a href>
    const vehiclesBtn = page.locator('button:has-text("Техника")').first();
    await expect(vehiclesBtn).toBeVisible({ timeout: 15000 });
    await vehiclesBtn.click();
    await page.waitForURL('**/vehicles', { timeout: 10000 });
    await expect(page).toHaveURL(/\/vehicles/);
  });
});
