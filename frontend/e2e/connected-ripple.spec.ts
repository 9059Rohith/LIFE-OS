import { test, expect } from "@playwright/test";

test("connected workspace tracks a verified action and focuses its app", async ({ page }) => {
  let verified = false;
  const event = () => ({
    id: "event-1", title: "Schedule changed", event_type: "meeting_change",
    source: "text", status: verified ? "resolved" : "awaiting_approval",
    created_at: "2026-09-17T10:00:00Z", version: 1, summary: "Schedule changed",
    simulation: false, entities: {}, context: [], timeline: [],
    actions: [{
      id: "action-1", application: "discord", type: "send", title: "Notify the team",
      reason: "Team schedule changed", target: "channel", arguments: {}, risk: "medium",
      status: verified ? "verified" : "awaiting_approval", requires_approval: true,
      reversible: false, dependencies: [], evidence: null, error: null, arguments_hash: "hash",
    }],
  });
  await page.route("**/api/session", (route) => route.fulfill({ json: {
    user: { id: "owner", name: "Owner" }, csrf_token: "test", mode: "live", voice_available: false,
  } }));
  await page.route("**/api/events", (route) => route.fulfill({ json: [event()] }));
  await page.route("**/api/integrations", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/apps/*", (route) => {
    const application = route.request().url().split("/").pop() || "";
    return route.fulfill({ json: {
      application, title: application === "discord" ? "#team" : application,
      items: application === "discord" ? [{ id: "message-1", author: "Teammate", content: "Meeting moved", date: "2026-09-17T10:00:00Z" }] : [],
    } });
  });

  await page.goto("/");
  await expect(page.getByLabel("Discord screen")).toBeVisible();
  await expect(page.getByLabel("Ripple effect", { exact: true })).toContainText("0/1 verified");
  await page.getByRole("button", { name: "View Discord for Notify the team" }).click();
  await expect(page.getByLabel("Discord screen")).toBeFocused();
  verified = true;
  await expect(page.getByLabel("Ripple effect", { exact: true })).toContainText("1/1 verified", { timeout: 8000 });
  await expect(page.getByRole("progressbar", { name: "Verified actions" })).toHaveAttribute("aria-valuenow", "1");
});

test("a saved event restores the consequence graph and timeline after refresh", async ({ page }) => {
  const saved = {
    id: "saved-event", title: "Client meeting moved to 14:00", event_type: "meeting_change",
    source: "text", status: "clarification_required", created_at: "2026-09-17T10:00:00Z",
    version: 1, summary: "Calendar target needs clarification", simulation: false,
    entities: { new_time: "14:00" }, actions: [], context: [],
    timeline: [{ id: "step", timestamp: "2026-09-17T10:00:00Z", stage: "planned", message: "Calendar target needs clarification" }],
  };
  await page.route("**/api/session", (route) => route.fulfill({ json: {
    user: { id: "owner", name: "Workspace" }, csrf_token: "test", mode: "live", voice_available: false,
  } }));
  await page.route("**/api/events", (route) => route.fulfill({ json: [saved] }));
  await page.goto("/");
  await page.getByRole("button", { name: "Overview" }).click();
  await expect(page.locator(".root-node")).toContainText(saved.title);
  await expect(page.locator(".timeline-item")).toContainText("Calendar target needs clarification");
  await page.reload();
  await page.getByRole("button", { name: "Overview" }).click();
  await expect(page.locator(".root-node")).toContainText(saved.title);
  await expect(page.locator(".timeline-item")).toContainText("Calendar target needs clarification");
});
