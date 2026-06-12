// Regression guard for the mobile viewport fix: the page must be a scrollable
// SPA and the footer (EIA source / raw-data link) must be reachable — not
// clipped by a pinned 100dvh / overflow:hidden shell.
import { test, expect } from '@playwright/test';
import { waitForApp } from './helpers.js';

test.beforeEach(async ({ page }) => {
  await page.route('**/ipapi.co/**', (r) => r.abort());
});

test('mobile: footer EIA/raw-data link is reachable (not clipped)', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile viewport only');

  await page.goto('/');
  await waitForApp(page);

  const link = page.locator('.site-footer a[href="data/data.json"]');
  await expect(link).toHaveCount(1);

  // The footer must not be display:none and must be reachable by scrolling.
  await link.scrollIntoViewIfNeeded();
  await expect(link).toBeVisible();
  await expect(link).toBeInViewport();
});
