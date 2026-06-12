// Playwright e2e config for the zero-build frontend.
// Serves frontend/ via a static server and runs the specs in frontend/e2e.
import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';

// Prefer Playwright's bundled Chromium; fall back to a system Chromium when the
// bundled browser can't be installed (e.g. an OS Playwright doesn't recognize).
// Override with PLAYWRIGHT_CHROMIUM_PATH if needed.
const SYSTEM_CHROMIUM = [
  process.env.PLAYWRIGHT_CHROMIUM_PATH,
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/snap/bin/chromium',
  '/usr/bin/google-chrome',
].find((p) => p && fs.existsSync(p));

const chromiumLaunch = SYSTEM_CHROMIUM
  ? {
      executablePath: SYSTEM_CHROMIUM,
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-setuid-sandbox',
      ],
    }
  : {};

export default defineConfig({
  testDir: './frontend/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:8080',
    trace: 'on-first-retry',
    // Block the service worker so route mocks (data.json) are deterministic —
    // SW-initiated fetches bypass page.route().
    serviceWorkers: 'block',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], launchOptions: chromiumLaunch } },
    // Pixel 5 is a Chromium-based mobile device (iPhone descriptors default to
    // WebKit, which isn't installed here); same small-viewport / touch semantics.
    { name: 'mobile',  use: { ...devices['Pixel 5'], launchOptions: chromiumLaunch } },
  ],
  webServer: {
    command: 'python3 -m http.server 8080 --directory frontend',
    url: 'http://localhost:8080',
    reuseExistingServer: true,
    timeout: 20_000,
  },
});
