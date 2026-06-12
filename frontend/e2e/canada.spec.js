// Canada must work: selecting a Canadian province shows a $/L price.
import { test, expect } from '@playwright/test';
import { waitForApp } from './helpers.js';

test.beforeEach(async ({ page }) => {
  await page.route('**/ipapi.co/**', (r) => r.abort());
});

test('selecting Ontario shows a per-litre price', async ({ page }) => {
  await page.goto('/');
  await waitForApp(page);

  // Open the location picker, filter to Ontario (so the option is in view on
  // the small mobile sheet), and select it.
  await page.locator('.chip').click();
  await page.locator('.loc-search').first().fill('Ontario');
  await page.locator('.loc-name', { hasText: 'Ontario' }).first().click();

  // Price label must render the Canadian unit.
  const unit = page.locator('.price-unit-inline');
  await expect(unit).toContainText('/L');

  // Sanity: a plausible Canadian pump price (CAD/L), not a $/gal number.
  const priceText = await page.locator('.price-number').first().innerText();
  const value = parseFloat(priceText.replace(/[^0-9.]/g, ''));
  expect(value).toBeGreaterThan(0.8);
  expect(value).toBeLessThan(3.0);
});
