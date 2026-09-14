import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";

test("deployed public demo requires login and resolves the hero event", async ({ page }) => {
  const passwordFile = process.env.PUBLIC_DEMO_PASSWORD_FILE;
  test.skip(!process.env.E2E_BASE_URL || !passwordFile, "Requires an explicit public demo target and password file");
  const password = readFileSync(passwordFile!, "utf8").trim();
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page.getByLabel("Workspace password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run hero demo" })).toHaveCount(0);
  await page.getByLabel("Workspace password").fill(password);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.getByRole("button", { name: "Run hero demo" })).toBeVisible();

  await page.getByRole("button", { name: "Run hero demo" }).click();
  await expect(page.getByRole("region", { name: "Consequence graph" })).toContainText("Flight");
  await page.getByRole("button", { name: /Approve all/ }).click();
  await page.getByRole("button", { name: "Execute approved", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Every action accounted for." })).toBeVisible();
  await expect(page.getByText("Resolved with read-back verification.")).toBeVisible();
  expect(pageErrors).toEqual([]);
});
