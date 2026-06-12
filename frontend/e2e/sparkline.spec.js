// The 2-week sparkline must render a real, non-flat trend, with unique gradient
// IDs (no duplicate-id rendering bug).
import { test, expect } from '@playwright/test';
import { waitForApp } from './helpers.js';

test.beforeEach(async ({ page }) => {
  await page.route('**/ipapi.co/**', (r) => r.abort());
});

test('sparkline polyline has more than one distinct y (not flat)', async ({ page }) => {
  await page.goto('/');
  await waitForApp(page);

  const poly = page.locator('.spark polyline').first();
  await expect(poly).toHaveCount(1);

  const points = await poly.getAttribute('points');
  const ys = points.trim().split(/\s+/).map((p) => parseFloat(p.split(',')[1]));
  const distinct = new Set(ys.map((y) => y.toFixed(2)));
  expect(distinct.size).toBeGreaterThan(1);
});

test('no duplicate sparkline gradient IDs in the DOM', async ({ page }) => {
  await page.goto('/');
  await waitForApp(page);

  const ids = await page.evaluate(() =>
    Array.from(document.querySelectorAll('linearGradient[id^="spark-"]')).map((n) => n.id)
  );
  expect(new Set(ids).size).toBe(ids.length);
});
