import { test, expect } from "@playwright/test";

test("desktop dock separates an uncertain send from a verified receipt", async ({ page }) => {
  await page.addInitScript(() => {
    const calls: { selected: string[]; viewport?: { width: number; height: number } } = { selected: [] };
    Object.assign(window, {
      __lifeosCalls: calls,
      lifeosDesktop: {
        select: (name: string) => calls.selected.push(name),
        setViewport: (bounds: { width: number; height: number }) => { calls.viewport = bounds; },
        reloadWorkspace: () => {}, reload: () => {}, onStatus: () => () => {},
      },
    });
  });
  await page.route("**/api/session", (route) => route.fulfill({ json: {
    user: { id: "owner", name: "Workspace" }, csrf_token: "test", mode: "live", voice_available: false,
  } }));
  await page.route("**/api/events", (route) => route.fulfill({ json: [{
    id: "event", title: "Flight time changed", event_type: "flight_change", source: "gmail",
    source_ref: { application: "gmail", record_id: "source-message-1" },
    status: "partial_failure", created_at: "2026-09-17T10:00:00Z", version: 1,
    summary: "A send needs manual review.", simulation: false, entities: {}, context: [], timeline: [],
    actions: [{
      id: "send", application: "whatsapp", type: "send", title: "Share the flight change",
      reason: "Known contact", target: "Family", arguments: { contact: "Family", body: "Flight changed" },
      risk: "high", status: "uncertain", requires_approval: true, reversible: false,
      dependencies: [], evidence: { verified: false }, error: "Delivery could not be confirmed",
      arguments_hash: "approved-hash",
    }],
  }] }));
  await page.goto("/desktop.html");
  await expect(page.getByText("source-message-1")).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Verified actions" })).toHaveAttribute("aria-valuenow", "0");
  await page.getByRole("button", { name: /Share the flight change/ }).click();
  await expect(page.getByText("Provider read-back did not verify this action.")).toBeVisible();
  await expect(page.getByText("Provider read-back verified")).toHaveCount(0);
  await page.getByRole("button", { name: "Open WhatsApp" }).click();
  const calls = await page.evaluate(() => (window as typeof window & { __lifeosCalls: {
    selected: string[]; viewport?: { width: number; height: number };
  } }).__lifeosCalls);
  expect(calls.selected[0]).toBe("lifeos");
  expect(calls.selected).toContain("whatsapp");
  expect(calls.viewport?.width).toBeGreaterThan(300);
  expect(calls.viewport?.height).toBeGreaterThan(180);
});

test("desktop dock discovers a newly signed-in workspace", async ({ page }) => {
  let signedIn = false;
  await page.addInitScript(() => {
    Object.assign(window, { lifeosDesktop: {
      select: () => {}, setViewport: () => {}, reloadWorkspace: () => {}, reload: () => {},
      onStatus: () => () => {},
    } });
  });
  await page.route("**/api/session", (route) => signedIn
    ? route.fulfill({ json: { user: { id: "owner", name: "Workspace" }, csrf_token: "test", mode: "live", voice_available: false } })
    : route.fulfill({ status: 401, json: { detail: "Sign in required" } }));
  await page.route("**/api/events", (route) => route.fulfill({ json: [] }));
  await page.goto("/desktop.html");
  await expect(page.getByRole("heading", { name: "Connect your workspace" })).toBeVisible();
  signedIn = true;
  await expect(page.getByLabel("What changed?")).toBeVisible({ timeout: 10000 });
});
