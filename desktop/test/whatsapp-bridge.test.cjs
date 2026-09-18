"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { inWhatsAppPage } = require("../whatsapp-bridge.cjs");

function installConversation(t, messages) {
  const previous = global.document;
  t.after(() => { global.document = previous; });
  const header = {
    querySelectorAll: () => [{ getAttribute: () => "Allowed chat", textContent: "Allowed chat" }],
  };
  const composer = {
    getAttribute: (name) => name === "contenteditable" ? "true" : "Type a message",
  };
  global.document = {
    querySelector: (selector) => selector === "#pane-side" ? {} : selector === "#main header" ? header : null,
    querySelectorAll: (selector) => {
      if (selector.includes("conversation-compose-box-input")) return [composer];
      if (selector === "#main .message-out[data-id]") return messages.map((message) => ({
        getAttribute: () => message.id,
        querySelector: (part) => {
          if (part === '[data-testid="selectable-text"]') return { innerText: message.text };
          if (part.includes("msg-check")) return message.sent ? {} : null;
          if (part.includes("msg-time")) return message.pending ? {} : null;
          return null;
        },
      }));
      if (selector === '#main [data-testid="msg-container"]') return [];
      return [];
    },
  };
}

test("WhatsApp verification waits for the exact outgoing message to acquire a sent indicator", async (t) => {
  const messages = [{ id: "new-id", text: "Approved message", sent: false, pending: true }];
  installConversation(t, messages);
  setTimeout(() => { messages[0].sent = true; messages[0].pending = false; }, 100);
  const answer = await inWhatsAppPage({
    operation: "verify", payload: { contact: "Allowed chat", id: "new-id", body: "Approved message" },
  });
  assert.deepEqual(answer, { ok: true, result: { verified: true, provider_id: "new-id" } });
});

test("WhatsApp send confirmation ignores a different message containing the approved body", async (t) => {
  const messages = [{ id: "wrong-id", text: "Approved message plus extra text", sent: true }];
  installConversation(t, messages);
  setTimeout(() => { messages.push({ id: "correct-id", text: "Approved message", sent: true }); }, 100);
  const answer = await inWhatsAppPage({
    operation: "confirm_send", payload: { contact: "Allowed chat", before: [], body: "Approved message", idempotency_key: "key" },
  });
  assert.deepEqual(answer, { ok: true, result: {
    id: "correct-id", contact: "Allowed chat", body: "Approved message", idempotency_key: "key",
  } });
});

test("WhatsApp verification reads the message-container layout used by the signed-in page", async (t) => {
  installConversation(t, []);
  const originalQuery = global.document.querySelectorAll;
  global.document.querySelectorAll = (selector) => {
    if (selector !== '#main [data-testid="msg-container"]') return originalQuery(selector);
    return [{
      querySelector: (part) => {
        if (part === '[data-icon="tail-out"]') return {};
        if (part === '[data-testid="selectable-text"]') return { innerText: "Approved message" };
        return null;
      },
      closest: () => ({
        getAttribute: () => "real-id",
        querySelector: () => ({ getAttribute: () => "Read" }),
      }),
    }];
  };
  const answer = await inWhatsAppPage({
    operation: "verify", payload: { contact: "Allowed chat", id: "real-id", body: "Approved message" },
  });
  assert.deepEqual(answer, { ok: true, result: { verified: true, provider_id: "real-id" } });
});
