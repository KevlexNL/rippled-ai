import { execSync } from 'child_process';
import path from 'path';

/**
 * Playwright global setup — runs before all test suites.
 * Kills orphaned browser/OpenClaw gateway processes that cause PortInUseError.
 */
export default function globalSetup() {
  const scriptPath = path.resolve(__dirname, '..', 'scripts', 'kill-browser-zombies.sh');
  try {
    execSync(`bash "${scriptPath}" --force`, {
      stdio: 'inherit',
      timeout: 15_000,
    });
  } catch {
    // Non-fatal — if cleanup fails, tests may still work if ports happen to be free
    console.warn('[global-setup] Browser zombie cleanup returned non-zero (may be fine if no zombies found)');
  }
}
