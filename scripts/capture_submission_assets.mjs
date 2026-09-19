import { createRequire } from "node:module";
import { mkdirSync, readdirSync, renameSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const baseURL = process.env.LIFEOS_CAPTURE_URL || "http://127.0.0.1:5175";
const paced = process.env.LIFEOS_CAPTURE_PACED === "true";
const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const screenshotDir = resolve(root, "docs/screenshots");
const demoDir = resolve(root, "docs/demo");
const videoDir = resolve(demoDir, "raw");

mkdirSync(screenshotDir, { recursive: true });
mkdirSync(videoDir, { recursive: true });

async function screenshot(page, name) {
  await page.screenshot({
    path: join(screenshotDir, name),
    fullPage: true,
    animations: "disabled",
  });
}

async function pause(ms) {
  if (paced) await new Promise((resolvePause) => setTimeout(resolvePause, ms));
}

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: videoDir, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();

await page.goto(baseURL, { waitUntil: "domcontentloaded" });
await page.getByRole("heading", { name: /Something changed/ }).waitFor();
await screenshot(page, "01-overview-empty.png");
await pause(1200);

await page.getByRole("button", { name: "Run hero demo" }).click();
await page.getByRole("button", { name: /Approve all/ }).waitFor();
await screenshot(page, "02-workflow-plan.png");
await pause(1200);

await page.getByRole("button", { name: "Review", exact: true }).first().click();
await page.getByRole("dialog").waitFor();
await screenshot(page, "03-action-review.png");
await pause(800);
await page.getByRole("button", { name: "Close", exact: true }).click();
await pause(400);

await page.getByRole("button", { name: /Approve all/ }).click();
await pause(800);
await page.getByRole("button", { name: "Execute approved", exact: true }).click();
await page.getByRole("heading", { name: "Every action accounted for." }).waitFor({ timeout: 20000 });
await screenshot(page, "03-verified-result.png");
await pause(800);

await page.getByRole("button", { name: "Demo applications", exact: true }).click();
await page.getByRole("heading", { name: "Inside the demo applications." }).waitFor();
await page.locator(".app-records .panel").first().waitFor();
await screenshot(page, "04-demo-applications.png");
await pause(800);

await page.getByRole("button", { name: "My work", exact: true }).click();
await page.getByRole("heading", { name: "Your work, connected." }).waitFor();
await screenshot(page, "05-my-work.png");
await page.getByRole("tab", { name: "Calendar", exact: true }).click();
await page.getByRole("heading", { name: "Next 14 days" }).waitFor();
await screenshot(page, "06-calendar.png");
await pause(800);

await page.getByRole("button", { name: "Integrations", exact: true }).click();
await page.getByRole("heading", { name: /Your connections\./ }).waitFor();
await page.locator(".integration-list .integration-row").first().waitFor();
await screenshot(page, "07-integrations.png");
await pause(800);

await page.getByRole("button", { name: "Audit trail", exact: true }).click();
await page.getByRole("heading", { name: "A record of every decision." }).waitFor();
await screenshot(page, "08-audit-trail.png");
await pause(800);

await page.getByRole("button", { name: "Settings", exact: true }).click();
await page.getByLabel("Display name").waitFor();
await screenshot(page, "09-settings.png");
await pause(800);

await page.getByRole("button", { name: "Overview", exact: true }).click();
await screenshot(page, "10-overview-complete.png");
await pause(800);

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(baseURL, { waitUntil: "domcontentloaded" });
await page.getByRole("heading", { name: /Something changed/ }).waitFor();
await screenshot(page, "11-mobile-overview.png");
await pause(800);

await context.close();
await browser.close();

const videos = readdirSync(videoDir).filter((file) => file.endsWith(".webm"));
if (videos.length) {
  const newest = videos
    .map((file) => ({ file, path: join(videoDir, file), mtime: statSync(join(videoDir, file)).mtimeMs }))
    .sort((a, b) => a.mtime - b.mtime)
    .at(-1);
  renameSync(newest.path, join(demoDir, "lifeos-demo-raw.webm"));
}

console.log(`Captured LIFEOS screenshots and raw demo video from ${baseURL}`);
