import { test as setup, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const AUTH_FILE = "e2e/.auth/user.json";
const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8000";
const FRONTEND_URL = process.env.E2E_BASE_URL || "http://localhost:3000";

async function waitForBackend(maxRetries = 30, delayMs = 2000): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const resp = await fetch(API_URL + "/api/v1/system/health", { signal: AbortSignal.timeout(3000) });
      if (resp.ok) {
        console.log("✅ Backend available");
        return;
      }
    } catch (e) {
      console.log("Health check failed:", (e as Error).message);
    }
    console.log("Waiting for backend... (" + (i + 1) + "/" + maxRetries + ")");
    await new Promise((r) => setTimeout(r, delayMs));
  }
  throw new Error("Backend not available at " + API_URL);
}

setup("authenticate as admin via API", async () => {
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
      console.log("Login attempt " + (attempt + 1) + " failed with status: " + response.status);
    } catch (e) {
      console.log("Login attempt " + (attempt + 1) + " failed: " + e);
      await new Promise((r) => setTimeout(r, 2000));
    }
  }

  expect(response?.ok).toBeTruthy();
  const data = await response!.json();

  const authDir = path.dirname(AUTH_FILE);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const storageState = {
    cookies: [],
    origins: [
      {
        origin: FRONTEND_URL,
        localStorage: [
          { name: "access_token", value: data.access_token },
          { name: "refresh_token", value: data.refresh_token },
        ],
      },
    ],
  };

  fs.writeFileSync(AUTH_FILE, JSON.stringify(storageState, null, 2));
  console.log("✅ Auth state saved to " + AUTH_FILE);
});
