import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Use saved auth state
    await page.context().addCookies([]);
  });

  test('should display key metrics', async ({ page }) => {
    await page.goto('/');

    // Welcome banner
    await expect(page.locator('text=Добро пожаловать')).toBeVisible({ timeout: 10_000 });

    // Key metric cards
    await expect(page.locator('text=Техника')).toBeVisible();
    await expect(page.locator('text=Заявки')).toBeVisible();
    await expect(page.locator('text=Общий доход')).toBeVisible();
  });

  test('should have period filter', async ({ page }) => {
    await page.goto('/');

    // Period selector inputs
    const dateInputs = page.locator('input[type="date"]');
    await expect(dateInputs).toHaveCount(2, { timeout: 10_000 });
  });

  test('should navigate via quick actions', async ({ page }) => {
    await page.goto('/');

    // Click vehicles quick action
    await page.click('text=Управление техникой');
    await page.waitForURL('**/vehicles');
    await expect(page).toHaveURL(/\/vehicles/);
  });
});
