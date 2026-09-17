const { test } = require("node:test");
const assert = require("node:assert/strict");
const { isAllowedNavigation, isExternalGoogleAuthorization } = require("../navigation.cjs");

const shellOrigin = "http://127.0.0.1:8010";
const providers = {
  discord: { origin: "https://discord.com" },
  whatsapp: { origin: "https://web.whatsapp.com" },
};
const allowed = (name, url) => isAllowedNavigation(name, url, shellOrigin, providers);

test("shell stays on LIFEOS and Google OAuth goes to the system browser", () => {
  assert.equal(allowed("shell", shellOrigin + "/desktop.html"), true);
  assert.equal(allowed("shell", "https://accounts.google.com/o/oauth2/v2/auth"), false);
  assert.equal(allowed("lifeos", shellOrigin + "/api/integrations/google/callback"), true);
  assert.equal(allowed("lifeos", "https://accounts.google.com/o/oauth2/v2/auth"), false);
  assert.equal(allowed("lifeos", "https://accounts.google.com.attacker.example/"), false);
  assert.equal(isExternalGoogleAuthorization("https://accounts.google.com/o/oauth2/v2/auth?state=abc"), true);
  assert.equal(isExternalGoogleAuthorization("https://accounts.google.com/other"), false);
  assert.equal(isExternalGoogleAuthorization("https://accounts.google.com.attacker.example/o/oauth2/v2/auth"), false);
});

test("provider views cannot navigate into LIFEOS or another provider", () => {
  assert.equal(allowed("discord", "https://discord.com/login"), true);
  assert.equal(allowed("whatsapp", "https://web.whatsapp.com/"), true);
  assert.equal(allowed("discord", shellOrigin + "/"), false);
  assert.equal(allowed("whatsapp", "https://discord.com/app"), false);
  assert.equal(allowed("whatsapp", "javascript:alert(1)"), false);
  assert.equal(allowed("unknown", "https://discord.com/app"), false);
});
