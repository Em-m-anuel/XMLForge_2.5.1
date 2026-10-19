import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 120 * 1000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: '../XMLForge/backend/.venv/bin/python e2e/run_backend.py',
      url: 'http://127.0.0.1:5000/health',
      reuseExistingServer: false,
      timeout: 120 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },
    {
      command: 'npm run dev -- --port 5173 --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 120 * 1000,
    },
  ],
});
