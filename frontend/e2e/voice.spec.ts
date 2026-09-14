import { test, expect } from "@playwright/test";
test("recorded voice shares planning and version-bound approval flow (speech API fixtures)", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["microphone"]);
  await page.route("**/api/session", async (route) => {
    const response = await route.fetch();
    const value = (await response.json()) as Record<string, unknown>;
    await route.fulfill({
      response,
      json: { ...value, voice_available: true },
    });
  });
  let transcript = "My flight AI-742 tomorrow moved to 6:40 AM.";
  let uploads = 0;
  await page.route("**/api/voice/transcribe", async (route) => {
    expect(route.request().headers()["content-type"]).toContain(
      "multipart/form-data",
    );
    expect(route.request().postDataBuffer()?.length).toBeGreaterThan(100);
    uploads++;
    await route.fulfill({ json: { text: transcript } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start voice input" }).click();
  await expect(
    page.getByRole("button", { name: "Stop recording" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Stop recording" }).click();
  await expect(
    page.getByRole("textbox", { name: "Tell LIFEOS what changed" }),
  ).toHaveValue(transcript);
  await page.getByRole("button", { name: "Analyze change" }).click();
  await expect(page.getByRole("button", { name: /Approve all/ })).toBeVisible();
  transcript = "Approve the plan.";
  await page.getByRole("button", { name: "Start voice input" }).click();
  await page.getByRole("button", { name: "Stop recording" }).click();
  await expect(page.getByText("Voice approval ready for review")).toBeVisible();
  transcript = "Confirm approval.";
  await page.getByRole("button", { name: "Start voice input" }).click();
  await page.getByRole("button", { name: "Stop recording" }).click();
  await expect(page.getByRole("button", { name: /Approve all/ })).toHaveCount(
    0,
  );
  transcript = "Execute approved plan.";
  await page.getByRole("button", { name: "Start voice input" }).click();
  await page.getByRole("button", { name: "Stop recording" }).click();
  await expect(
    page.getByRole("heading", { name: "Every action accounted for." }),
  ).toBeVisible();
  expect(uploads).toBe(4);
  let spoken = false;
  await page.route("**/api/voice/speak", async (route) => {
    const body = route.request().postDataJSON() as { text: string };
    expect(body.text).toContain("verified");
    spoken = true;
    const wav = Buffer.alloc(44 + 64000);
    wav.write("RIFF", 0);
    wav.writeUInt32LE(wav.length - 8, 4);
    wav.write("WAVEfmt ", 8);
    wav.writeUInt32LE(16, 16);
    wav.writeUInt16LE(1, 20);
    wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(16000, 24);
    wav.writeUInt32LE(32000, 28);
    wav.writeUInt16LE(2, 32);
    wav.writeUInt16LE(16, 34);
    wav.write("data", 36);
    wav.writeUInt32LE(64000, 40);
    await route.fulfill({ contentType: "audio/wav", body: wav });
  });
  await page.getByRole("button", { name: "Read summary aloud" }).click();
  await expect(
    page.getByRole("button", { name: "Stop speaking" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Stop speaking" }).click();
  await expect(
    page.getByRole("button", { name: "Read summary aloud" }),
  ).toBeVisible();
  expect(spoken).toBe(true);
});
test("a bare yes never authorizes a plan", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Run hero demo" }).click();
  await page
    .getByRole("textbox", { name: "Tell LIFEOS what changed" })
    .fill("Yes");
  await page.getByRole("button", { name: "Analyze change" }).click();
  await expect(page.getByRole("alert")).toContainText("CLARIFICATION_REQUIRED");
  await expect(
    page.getByRole("button", { name: "Execute approved" }),
  ).toHaveCount(0);
});
