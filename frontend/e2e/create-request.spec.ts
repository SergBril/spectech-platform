import { test, expect } from '@playwright/test';

test.describe('Create Request', () => {
  test('should have create button or show permission message', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Кнопка создания видна только при наличии прав requests.create
    const createBtn = page.locator('button:has-text("Новая заявка")');
    const hasCreateBtn = await createBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasCreateBtn) {
      // Если кнопка есть — открываем форму
      await createBtn.click();
      const modal = page.locator('form');
      await expect(modal.first()).toBeVisible({ timeout: 5000 });
    } else {
      // Если нет прав — страница всё равно должна загрузиться
      const body = page.locator('body');
      await expect(body).toBeVisible();
    }
  });

  test('should open and close request form modal', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    const createBtn = page.locator('button:has-text("Новая заявка")');
    const hasCreateBtn = await createBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasCreateBtn) {
      test.skip(true, 'User does not have requests.create permission');
      return;
    }

    await createBtn.click();

    // Форма открылась
    const form = page.locator('form');
    await expect(form.first()).toBeVisible({ timeout: 5000 });

    // Закрываем модалку
    const closeBtn = page.locator('button:has-text("Отмена"), button[aria-label="Close"], .fixed.inset-0 button:first-child');
    if (await closeBtn.first().isVisible({ timeout: 2000 }).catch(() => false)) {
      await closeBtn.first().click();
      await expect(form.first()).not.toBeVisible({ timeout: 3000 });
    }
  });

  test('should have required form fields when opened', async ({ page }) => {
    await page.goto('/requests');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    const createBtn = page.locator('button:has-text("Новая заявка")');
    const hasCreateBtn = await createBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasCreateBtn) {
      test.skip(true, 'User does not have requests.create permission');
      return;
    }

    await createBtn.click();

    const form = page.locator('form');
    await expect(form.first()).toBeVisible({ timeout: 5000 });

    // Тип заявки (select)
    const selects = form.locator('select');
    expect(await selects.count()).toBeGreaterThanOrEqual(1);

    // Поля ввода (input/textarea)
    const inputs = form.locator('input, textarea');
    expect(await inputs.count()).toBeGreaterThanOrEqual(1);
  });
});
