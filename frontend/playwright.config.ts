import { defineConfig } from "@playwright/test";

const isCI = Boolean(process.env.CI && process.env.CI !== "false");

export default defineConfig({
  testDir: "./tests", fullyParallel: false, workers: 1, timeout: isCI ? 60_000 : 30_000,
  // next dev compiles routes on first access on a fresh CI runner.
  expect: {timeout: isCI ? 15_000 : 5_000},
  use: {baseURL: "http://127.0.0.1:28100", browserName: "chromium", channel: process.env.PLAYWRIGHT_CHANNEL || "chrome", trace: "retain-on-failure"},
  webServer: [
    {command: "node tests/mock-backend.mjs", url: "http://127.0.0.1:28101/health", reuseExistingServer: false},
    {command: "npm run dev -- --hostname 127.0.0.1 --port 28100", url: "http://127.0.0.1:28100/login", reuseExistingServer: false, timeout: 120_000,
      env: {API_INTERNAL_URL: "http://127.0.0.1:28101", APP_ORIGIN: "http://127.0.0.1:28100", NEXT_DIST_DIR: ".next-test"}},
  ],
});
