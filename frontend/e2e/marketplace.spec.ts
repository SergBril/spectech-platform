import { test, expect } from '@playwright/test';

test.describe('Marketplace Page', () => {
  test('should load marketplace page', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    const body = page.locator('body');
    await expect(body).toBeVisible({ timeout: 10000 });
  });

  test('should have category filter', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Фильтр по категории
    const categorySelect = page.locator('select');
    const hasFilter = await categorySelect.count() > 0;
    expect(hasFilter).toBeTruthy();
  });

  test('should have cross-category toggle', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Кнопка кросс-категорий
    const crossCatBtn = page.locator('button:has-text("Кросс-категории")');
    const hasToggle = await crossCatBtn.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasToggle).toBeTruthy();
  });

  test('should display listings or empty state', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Должен быть либо список карточек, либо сообщение о пустом списке
    const content = page.locator('[class*="card"], [class*="listing"], [class*="empty"], [class*="no-data"], table, p');
    const count = await content.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
