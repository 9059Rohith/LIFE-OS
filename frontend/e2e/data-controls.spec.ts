import { test, expect } from "@playwright/test";

test("monitoring is opt-in and privacy deletion requires explicit confirmation", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Integrations", exact: true }).click();
  const monitor = page.getByRole("region", { name: "Source monitoring" });
  await expect(
    monitor.getByRole("checkbox", { name: "Enable monitoring" }),
  ).not.toBeChecked();
  await expect(
    monitor.getByRole("button", { name: "Scan now", exact: true }),
  ).toBeDisabled();
  await monitor.getByRole("checkbox", { name: "Enable monitoring" }).check();
  await monitor.getByRole("button", { name: "Save monitoring" }).click();
  await expect(
    monitor.getByRole("button", { name: "Save monitoring" }),
  ).toBeEnabled();
  await expect
    .poll(
      async () =>
        (await (await page.request.get("/api/ingestion")).json()).enabled,
    )
    .toBe(true);
  await monitor.getByRole("checkbox", { name: "Enable monitoring" }).uncheck();
  await monitor.getByRole("button", { name: "Save monitoring" }).click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get("/api/ingestion")).json()).enabled,
    )
    .toBe(false);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const controls = page.getByRole("region", { name: "Data controls" });
  await expect(
    controls.getByRole("button", { name: "Delete workspace data" }),
  ).toBeDisabled();
  const download = page.waitForEvent("download");
  await controls.getByRole("button", { name: "Export workspace" }).click();
  expect((await download).suggestedFilename()).toBe("lifeos-workspace.json");
  await controls
    .getByLabel("Type DELETE MY DATA to erase this workspace")
    .fill("DELETE MY DATA");
  await expect(
    controls.getByRole("button", { name: "Delete workspace data" }),
  ).toBeEnabled();
  // Actual delete is exercised against isolated backend fixtures; do not erase
  // an operator's browser account when this suite is pointed at a live host.
});
