// GasBuddy deep-link behaviour: with a known cheapest station the button must
// deep-link to that station; without one it falls back to a region search URL.
import { test, expect } from '@playwright/test';
import { waitForApp, mockData, clickGasBuddy } from './helpers.js';

test.beforeEach(async ({ page }) => {
  await page.route('**/ipapi.co/**', (r) => r.abort());
  // Capture window.open targets without actually opening tabs.
  await page.addInitScript(() => {
    window.__opened = [];
    window.open = (url) => { window.__opened.push(url); return null; };
  });
});

test.use({ permissions: ['geolocation'], geolocation: { latitude: 37.77, longitude: -122.42 } });

test('deep-links to the cheapest station when one is known', async ({ page }) => {
  await mockData(page, (json) => {
    const ca = json.regions.find((r) => r.id === 'ca');
    ca.lowStation = { id: '12345', name: 'Costco', price: 4.31,
                      lat: 37.77, lng: -122.42,
                      url: 'https://www.gasbuddy.com/station/12345' };
  });
  await page.goto('/');
  await waitForApp(page);

  await clickGasBuddy(page);
  await expect.poll(() => page.evaluate(() => window.__opened)).toContain(
    'https://www.gasbuddy.com/station/12345'
  );
});

test('falls back to a region search URL when no station is known', async ({ page }) => {
  await mockData(page, (json) => {
    for (const r of json.regions) delete r.lowStation;
  });
  await page.goto('/');
  await waitForApp(page);

  await clickGasBuddy(page);
  await expect.poll(() => page.evaluate(() => window.__opened.length)).toBeGreaterThan(0);
  const urls = await page.evaluate(() => window.__opened);
  expect(urls.some((u) => u.includes('gasbuddy.com'))).toBeTruthy();
  expect(urls.some((u) => u.includes('/station/'))).toBeFalsy();
});
