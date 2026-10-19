import { test as setup, expect } from "@playwright/test";

const AUTH_FILE = "e2e/.auth/user.json";
const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8000";
const FRONTEND_URL = process.env.E2E_BASE_URL || "http://localhost:3000";

async function waitForBackend(maxRetries = 30, delayMs = 2000): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const resp = await fetch(API_URL + "/api/v1/system/health", { signal: AbortSignal.timeout(3000) });
      if (resp.ok) return;
    } catch {}
    console.log("Waiting for backend... (" + (i + 1) + "/" + maxRetries + ")");
    await new Promise((r) => setTimeout(r, delayMs));
  }
  throw new Error("Backend not available at " + API_URL + " after " + (maxRetries * delayMs / 1000) + "s");
}

setup("authenticate as admin via API", async ({ browser }) => {
  await waitForBackend();

  let response: Response | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      response = await fetch(API_URL + "/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "admin@spectech.dev", password: "admin123" }),
        signal: AbortSignal.timeout(10000),
      });
      if (response.ok) break;
    } catch (e) {
      console.log("Login attempt " + (attempt + 1) + " failed: " + e);
      await new Promise((r) => setTimeout(r, 2000));
    }
  }

  expect(response?.ok).toBeTruthy();
  const data = await response!.json();
  const access_token = data.access_token;
  const refresh_token = data.refresh_token;

  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(FRONTEND_URL + "/login");
  await page.evaluate((tokens) => {
    localStorage.setItem("access_token", tokens.access);
    localStorage.setItem("refresh_token", tokens.refresh);
  }, { access: access_token, refresh: refresh_token });

  await context.storageState({ path: AUTH_FILE });
  await context.close();
});
