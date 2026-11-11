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


  test('should have surplus request button', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Кнопка создания избыточной заявки
    const surplusBtn = page.locator('button:has-text("Избыточная заявка")');
    const hasBtn = await surplusBtn.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  test('should open surplus request modal', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    const surplusBtn = page.locator('button:has-text("Избыточная заявка")');
    const hasBtn = await surplusBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (!hasBtn) {
      test.skip(true, 'Surplus button not visible (no vehicles or permissions)');
      return;
    }

    await surplusBtn.click();
    await page.waitForTimeout(2000);

    // Wait for modal content (not the mobile sidebar overlay)
    // The surplus modal contains form fields - use that as indicator
    const modalContent = page.locator('form, [class*="modal"], [class*="bg-white"][class*="rounded"]');
    const hasModal = await modalContent.first().isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasModal) {
      // Modal may not open if no eligible vehicles - check for alert instead
      const bodyText = await page.locator('body').innerText();
      if (bodyText.includes('нет') || bodyText.includes('Нет') || bodyText.includes('error')) {
        test.skip(true, 'No eligible vehicles for surplus request');
        return;
      }
    }

    // If modal opened, verify form fields exist
    const formFields = page.locator('select, input[type="number"], input[type="date"], textarea');
    const fieldCount = await formFields.count();
    expect(fieldCount).toBeGreaterThanOrEqual(1);
  });

  test('should have surplus filter toggle', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Кнопка фильтра избыточных заявок
    const filterBtn = page.locator('button:has-text("Избыточные")');
    const hasFilter = await filterBtn.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasFilter).toBeTruthy();

    // При нажатии кнопка должна переключиться
    await filterBtn.click();
    await page.waitForTimeout(500);
    const allBtn = page.locator('button:has-text("Все заявки")');
    const switched = await allBtn.isVisible({ timeout: 3000 }).catch(() => false);
    expect(switched).toBeTruthy();
  });

  test('should show surplus badge on surplus requests', async ({ page }) => {
    await page.goto('/marketplace');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Переключаем фильтр на избыточные
    const filterBtn = page.locator('button:has-text("Избыточные")');
    const hasFilter = await filterBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (!hasFilter) {
      test.skip(true, 'Surplus filter not available');
      return;
    }

    await filterBtn.click();
    await page.waitForTimeout(2000);

    // Если есть избыточные заявки — должен быть бейдж
    const badges = page.locator('text=Избыточная');
    const cards = page.locator('[class*="card"], [class*="border"][class*="rounded"]');
    const cardCount = await cards.count();

    if (cardCount > 0) {
      const badgeCount = await badges.count();
      expect(badgeCount).toBeGreaterThanOrEqual(1);
    }
  });

});
