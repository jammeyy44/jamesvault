import { defineConfig } from "@playwright/test";

// Expects the Flask API on :8080 (seeded with `python seed_site.py --dev-sample`) and the web app on :3000.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  workers: 1,
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:3000" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true } },
  ],
});
