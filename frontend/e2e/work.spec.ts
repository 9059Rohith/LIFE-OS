import { test, expect } from "@playwright/test";

test("work records persist across connected modules and refresh", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "My work" }).click();
  await expect(page.getByText("No tasks yet.")).toBeVisible();
  const today = await page.evaluate(() => {
    const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
    const value = (type: string) => parts.find((part) => part.type === type)!.value;
    return `${value("year")}-${value("month")}-${value("day")}`;
  });

  await page.getByRole("tab", { name: /Projects/ }).click();
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Launch workspace");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Launch workspace" })).toBeVisible();

  await page.getByRole("tab", { name: /Goals/ }).click();
  await page.getByRole("button", { name: "New goal" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Ship release");
  await page.getByRole("textbox", { name: "Target date" }).fill(today);
  await page.getByRole("combobox", { name: "Project" }).selectOption({ label: "Launch workspace" });
  await page.getByRole("button", { name: "Save", exact: true }).click();

  await page.getByRole("tab", { name: /Tasks/ }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Verify persistence");
  await page.getByRole("textbox", { name: "Due date" }).fill(today);
  await page.getByRole("combobox", { name: "Goal" }).selectOption({ label: "Ship release" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("region", { name: "Reminders from saved work" })).toContainText("Due today");
  await page.getByRole("button", { name: "Complete Verify persistence" }).click();
  await expect(page.getByRole("region", { name: "Reminders from saved work" })).toHaveCount(0);
  await expect(page.getByText("Completed tasks").locator("..").getByText("1")).toBeVisible();

  await page.getByRole("tab", { name: /Habits/ }).click();
  await page.getByRole("button", { name: "New habit" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Review progress");
  await page.getByRole("combobox", { name: "Goal" }).selectOption({ label: "Ship release" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("region", { name: "Reminders from saved work" })).toContainText("Habit check-in due today");
  await page.getByRole("button", { name: "Check in" }).click();
  await expect(page.getByRole("region", { name: "Reminders from saved work" })).toHaveCount(0);
  await expect(page.getByText("Habit check-ins").locator("..").getByText("1")).toBeVisible();

  await page.getByRole("tab", { name: /Notes/ }).click();
  await page.getByRole("button", { name: "New note" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Release evidence");
  await page.getByRole("textbox", { name: "Note" }).fill("Saved in the workspace database.");
  await page.getByRole("combobox", { name: "Task" }).selectOption({ label: "Verify persistence" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Release evidence" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "My work" }).click();
  await page.getByRole("tab", { name: /Notes/ }).click();
  await expect(page.getByRole("heading", { name: "Release evidence" })).toBeVisible();
  await page.getByRole("tab", { name: /Projects/ }).click();
  await expect(page.getByText("1/1 tasks done")).toBeVisible();
  await page.getByRole("tab", { name: "Calendar" }).click();
  await expect(page.getByRole("region", { name: "Calendar agenda" })).toContainText("Verify persistence");
  await expect(page.getByRole("region", { name: "Calendar agenda" })).toContainText("Ship release");
  expect(errors).toEqual([]);
});

test("work area is usable on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "My work" }).click();
  await expect(page.getByRole("heading", { name: "Make progress visible." })).toBeVisible();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Review the cross-module persistence and responsive layout after a narrow-screen refresh");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Review the cross-module persistence/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
