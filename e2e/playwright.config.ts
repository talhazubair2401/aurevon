import { defineConfig, devices } from "@playwright/test";

// The stack must already be running behind the proxy (docker compose -f infra/compose.yaml up).
export default defineConfig({
  testDir: "tests",
  outputDir: "test-results",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // The staff journey creates the first Owner, so it runs once, on desktop.
    { name: "phone", use: { ...devices["Pixel 7"] }, testIgnore: /staff\.spec\.ts/ },
  ],
});
