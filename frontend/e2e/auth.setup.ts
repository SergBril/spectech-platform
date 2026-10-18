import { test as setup, expect } from "@playwright/test";

const AUTH_FILE = "e2e/.auth/user.json";



setup("authenticate as admin via API", async ({ browser }) => {

  // Login via API

  const response = await fetch("http://127.0.0.1:8000/api/v1/auth/login", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify({ email: "admin@spectech.dev", password: "admin123" }),  // pragma: allowlist secret

  });

  expect(response.ok).toBeTruthy();

  const { access_token, refresh_token } = await response.json();



  // Create browser context with tokens in localStorage

  const context = await browser.newContext();

  const page = await context.newPage();

  await page.goto("http://localhost:3000/login");

  await page.evaluate((tokens) => {

    localStorage.setItem("access_token", tokens.access);

    localStorage.setItem("refresh_token", tokens.refresh);

  }, { access: access_token, refresh: refresh_token });



  // Save storage state for other tests

  await context.storageState({ path: AUTH_FILE });

  await context.close();

});
