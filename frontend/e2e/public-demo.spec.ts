import { test, expect } from "@playwright/test";

test("deployed public demo opens without owner login and resolves the hero event", async ({ page }) => {
  test.skip(!process.env.E2E_BASE_URL, "Requires an explicit public demo target");
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Try interactive demo" })).toBeVisible();
  await page.getByRole("button", { name: "Try interactive demo" }).click();
  await expect(page.getByRole("button", { name: "Run hero demo" })).toBeVisible();

  await page.getByRole("button", { name: "Run hero demo" }).click();
  await expect(page.getByRole("region", { name: "Consequence graph" })).toContainText("Flight");
  await page.getByRole("button", { name: /Approve all/ }).click();
  await page.getByRole("button", { name: "Execute approved", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Every action accounted for." })).toBeVisible();
  await expect(page.getByText("Resolved with read-back verification.")).toBeVisible();
  expect(pageErrors).toEqual([]);
});
