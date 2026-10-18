import { test as setup, expect } from "@playwright/test";

const AUTH_FILE = "e2e/.auth/user.json";



setup("authenticate as admin via API", async ({ request }) => {

  const response = await request.post("http://127.0.0.1:8000/api/v1/auth/login", {

    data: { email: "admin@spectech.dev", password: "admin123"  # pragma: allowlist secret },

  });

  expect(response.ok()).toBeTruthy();

  const body = await response.json();

  await request.storageState({ path: AUTH_FILE });

});
