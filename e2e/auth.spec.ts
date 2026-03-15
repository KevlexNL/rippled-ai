import { test, expect } from '@playwright/test';

test.describe('Auth flow', () => {
  test('login page loads and shows expected UI', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Rippled' })).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'notreal@example.com');
    await page.fill('#password', 'wrongpassword');
    await page.click('button[type="submit"]');
    // Supabase returns an error — expect the red error banner to appear
    await expect(page.locator('.bg-red-50')).toBeVisible({ timeout: 8_000 });
  });

  test('forgot password link navigates correctly', async ({ page }) => {
    await page.goto('/login');
    await page.click('text=Forgot password?');
    await expect(page).toHaveURL(/\/forgot-password/);
  });

  test('sign up link navigates correctly', async ({ page }) => {
    await page.goto('/login');
    await page.click('text=Sign up');
    await expect(page).toHaveURL(/\/signup/);
  });

  test('unauthenticated users are redirected to /login from /', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
  });

  test('login with valid credentials', async ({ page }) => {
    const email = process.env.TEST_EMAIL;
    const password = process.env.TEST_PASSWORD;

    test.skip(!email || !password, 'TEST_EMAIL / TEST_PASSWORD not set — skipping live auth test');

    await page.goto('/login');
    await page.fill('#email', email!);
    await page.fill('#password', password!);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 10_000 });
    // Should land on dashboard or onboarding
    expect(['/', '/onboarding'].some((p) => page.url().endsWith(p))).toBeTruthy();
  });
});
