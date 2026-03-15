import { Page } from '@playwright/test';

/**
 * Log in as a test user via the UI.
 * Set TEST_EMAIL and TEST_PASSWORD env vars, or provide them directly.
 */
export async function loginAs(page: Page, email?: string, password?: string) {
  const e = email || process.env.TEST_EMAIL || '';
  const p = password || process.env.TEST_PASSWORD || '';

  await page.goto('/login');
  await page.fill('#email', e);
  await page.fill('#password', p);
  await page.click('button[type="submit"]');
  // Wait for redirect away from /login
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 10_000 });
}
