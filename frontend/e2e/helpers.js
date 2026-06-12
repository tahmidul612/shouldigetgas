// Shared e2e helpers.
import { expect } from '@playwright/test';

// Wait until the React app has rendered its real UI (not the loading screen).
export async function waitForApp(page) {
  await expect(page.locator('.price-number')).toBeVisible({ timeout: 15_000 });
}

// Click the *visible* GasBuddy button (the desktop hero button is display:none
// on mobile and vice-versa). getByRole skips display:none elements.
export async function clickGasBuddy(page) {
  const btn = page.getByRole('button', { name: /cheapest station|stations on GasBuddy/i });
  await btn.first().scrollIntoViewIfNeeded();
  await btn.first().click();
}

// Intercept data/data.json so a test can inject deterministic fixtures
// (e.g. a lowStation) regardless of what the backend produced.
export async function mockData(page, mutate) {
  await page.route('**/data/data.json', async (route) => {
    const res = await route.fetch();
    const json = await res.json();
    mutate(json);
    await route.fulfill({ response: res, body: JSON.stringify(json) });
  });
}
