import { test as setup } from "@playwright/test";
const AUTH_FILE = "e2e/.auth/user.json";
setup("authenticate as admin", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[type=\"email\"]", "admin@spectech.dev");
  await page.fill("input[type=\"password\"]", "admin123");
  await page.click("button[type=\"submit\"]");
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 30_000 });
  await page.context().storageState({ path: AUTH_FILE });
});
