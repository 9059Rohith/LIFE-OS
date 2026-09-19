import { defineConfig, devices } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const virtualPython = process.platform === "win32"
  ? resolve(projectRoot, ".venv/Scripts/python.exe")
  : resolve(projectRoot, ".venv/bin/python");
const python = existsSync(virtualPython) ? virtualPython : process.platform === "win32" ? "python" : "python3";
const testBackend = "http://127.0.0.1:8013";
const frontendPort = process.env.E2E_PORT || "5173";
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    launchOptions: {
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
      ],
    },
    baseURL: process.env.E2E_BASE_URL || frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1512, height: 1050 },
      },
    },
  ],
  webServer: process.env.E2E_BASE_URL ? undefined : [
    {
      command: `"${python}" -m uvicorn lifeos.main:app --app-dir backend --host 127.0.0.1 --port 8013`,
      cwd: projectRoot,
      env: {
        LIFEOS_MODE: "demo", LIFEOS_ENVIRONMENT: "test",
        LIFEOS_DATABASE_URL: `sqlite:///./.private/e2e-${process.pid}.db`, LIFEOS_PUBLIC_DEMO: "false",
        LIFEOS_AUTH_PASSWORD: "", LIFEOS_ENCRYPTION_KEY: "",
        LIFEOS_ALLOWED_ORIGINS: JSON.stringify([frontendUrl, testBackend]),
      },
      url: testBackend + "/health",
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --port ${frontendPort}`,
      env: { LIFEOS_API_URL: testBackend },
      url: frontendUrl,
      reuseExistingServer: false,
    },
  ],
  timeout: 30000,
});
