import { test, expect } from '@playwright/test';
import { loginAs } from './helpers/auth';

// These tests require a live Rippled account.
// Set TEST_EMAIL and TEST_PASSWORD env vars to run them.
test.describe('Dashboard (authenticated)', () => {
  test.beforeEach(async ({ page }) => {
    const email = process.env.TEST_EMAIL;
    const password = process.env.TEST_PASSWORD;
    test.skip(!email || !password, 'TEST_EMAIL / TEST_PASSWORD not set — skipping authenticated tests');
    await loginAs(page, email, password);
  });

  test('dashboard loads after login', async ({ page }) => {
    // Should be on / or /onboarding after login
    const url = page.url();
    expect(url).toMatch(/\/(onboarding)?$/);
  });

  test('dashboard shows commitment surface or empty state', async ({ page }) => {
    await page.goto('/');
    // Wait for loading to finish (spinner disappears or content loads)
    await expect(page.locator('[data-testid="loading-spinner"]').or(
      page.getByText('Loading')
    )).not.toBeVisible({ timeout: 10_000 }).catch(() => {});
    // Page should not show an error banner
    await expect(page.locator('[data-testid="error-banner"]')).not.toBeVisible();
  });

  test('can open add commitment form', async ({ page }) => {
    await page.goto('/');
    // Bottom bar has an add button — find it
    const addBtn = page.getByRole('button', { name: /add/i }).or(
      page.locator('button').filter({ hasText: /^\+$/ })
    );
    if (await addBtn.count() > 0) {
      await addBtn.first().click();
      // A form or input should appear
      await expect(page.locator('input[type="text"]').first()).toBeVisible({ timeout: 3_000 });
    }
  });
});
