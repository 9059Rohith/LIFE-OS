import { test, expect } from "@playwright/test";

test("a disconnected provider clears its earlier content and shows setup guidance", async ({ page }) => {
  let connected = true;
  const integrations = () => (["discord", "gmail", "whatsapp", "calendar", "drive"].map((id) => ({
    id, name: id, mode: "live", description: "Connection check completed.",
    status: id === "gmail" && connected ? "read_access_verified" : "not_connected",
  })));
  await page.route("**/api/session", (route) => route.fulfill({ json: {
    user: { id: "owner", name: "Workspace" }, csrf_token: "test", mode: "live", voice_available: false,
  } }));
  await page.route("**/api/events", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/integrations/check", (route) => {
    connected = false;
    return route.fulfill({ json: integrations() });
  });
  await page.route("**/api/integrations", (route) => route.fulfill({ json: integrations() }));
  await page.route("**/api/apps/gmail/message", (route) => route.fulfill({ json: {
    id: "message", from: "sender@example.com", to: "owner@example.com",
    subject: "Private account message", date: "2026-09-17T10:00:00Z", body: "Private body",
  } }));
  await page.route("**/api/apps/*", (route) => {
    const name = route.request().url().split("/").pop() || "";
    return connected && name === "gmail"
      ? route.fulfill({ json: { application: name, title: "Inbox", items: [{
          id: "message", from: "sender@example.com", subject: "Private account message",
          preview: "Private preview", date: "2026-09-17T10:00:00Z",
        }] } })
      : route.fulfill({ status: 502, json: { detail: "AUTHENTICATION_ERROR" } });
  });
  await page.goto("/");
  await expect(page.getByText("Private account message").first()).toBeVisible();
  await page.getByRole("button", { name: "Check connections" }).click();
  await expect(page.getByText("Connect Google in Integrations to show your real Gmail data.")).toBeVisible();
  await expect(page.getByText("Private account message")).toHaveCount(0);
  await expect(page.getByText("Private body")).toHaveCount(0);
});
