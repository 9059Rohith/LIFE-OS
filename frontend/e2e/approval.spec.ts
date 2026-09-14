import { test, expect } from "@playwright/test";
test("individual approval executes only selected mutations; edited content invalidates approval", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Run hero demo" }).click();
  await expect(
    page.getByRole("button", { name: "Execute approved" }),
  ).toHaveCount(0);
  const calendar = page
    .locator(".approval-row")
    .filter({ hasText: "Move client meeting" });
  await calendar.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("button", { name: "Execute approved" }).click();
  await expect(calendar).toContainText("verified");
  const email = page
    .locator(".approval-row")
    .filter({ hasText: "Send the client" });
  await expect(email).toContainText("awaiting approval");
  await email.getByRole("button", { name: "Review", exact: true }).click();
  await page.getByRole("button", { name: "Edit action" }).click();
  const editor = page.getByLabel("Action arguments (JSON)");
  const argumentsValue = JSON.parse(await editor.inputValue()) as Record<
    string,
    unknown
  >;
  argumentsValue.body =
    String(argumentsValue.body) + " Please confirm your availability.";
  await editor.fill(JSON.stringify(argumentsValue, null, 2));
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await email.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Please confirm your availability.",
  );
  await page.getByRole("button", { name: "Reject action" }).click();
  await expect(email).toContainText("rejected");
  await page.getByRole("button", { name: /Approve all/ }).click();
  await page.getByRole("button", { name: "Execute approved" }).click();
  await expect(
    page.getByRole("heading", { name: "Every action accounted for." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Undo reversible changes" }).click();
  await expect(
    page.getByRole("heading", { name: "This plan is closed." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Execute approved" }),
  ).toHaveCount(0);
});
