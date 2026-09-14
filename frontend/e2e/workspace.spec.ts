import { test, expect } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("workspace navigation ignores stale page requests", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let finishIntegrations!: () => void;
  let finishSettings!: () => void;
  const integrationsGate = new Promise<void>((resolve) => {
    finishIntegrations = resolve;
  });
  const settingsGate = new Promise<void>((resolve) => {
    finishSettings = resolve;
  });
  await page.route("**/api/integrations", async (route) => {
    await integrationsGate;
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/settings", async (route) => {
    await settingsGate;
    await route.fulfill({
      json: { name: "Current workspace", timezone: "UTC", retention_days: 14 },
    });
  });
  try {
    await page.goto("/");
    const integrationsRequest = page.waitForRequest("**/api/integrations");
    await page
      .getByRole("button", { name: "Integrations", exact: true })
      .click();
    await integrationsRequest;
    const settingsRequest = page.waitForRequest("**/api/settings");
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await settingsRequest;
    const integrationsResponse = page.waitForResponse("**/api/integrations");
    finishIntegrations();
    await integrationsResponse;
    await expect(page.getByText("Loading workspace…")).toBeVisible();
    await expect(page.getByLabel("Display name")).toBeHidden();
    finishSettings();
    await expect(page.getByLabel("Display name")).toHaveValue(
      "Current workspace",
    );
    await expect(page.getByLabel("Time zone")).toHaveValue("UTC");
    await expect(page).toHaveTitle(/LIFEOS/);
    await expect(page.locator("vite-error-overlay")).toHaveCount(0);
    expect(errors).toEqual([]);
    await page.screenshot({
      path: join(tmpdir(), "lifeos-workspace-settings.png"),
      fullPage: true,
    });
  } finally {
    finishIntegrations();
    finishSettings();
  }
});
