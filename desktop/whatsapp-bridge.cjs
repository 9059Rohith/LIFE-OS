"use strict";

// Runs inside the signed-in WhatsApp Web view. No account tokens leave its
// persistent Electron session; only the allowlisted chat is read or changed.
async function inWhatsAppPage(job) {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const fail = (code, attempted = false) => ({ ok: false, error_code: code, attempted });
  const { operation, payload } = job;
  const contact = payload?.contact;
  if (!contact || typeof contact !== "string" || contact.length > 200) return fail("AUTHORIZATION_ERROR");
  if (!["check", "read", "send", "confirm_send", "verify"].includes(operation)) return fail("AUTHORIZATION_ERROR");

  const waitFor = async (test, milliseconds) => {
    const deadline = Date.now() + milliseconds;
    while (Date.now() < deadline) {
      const found = test();
      if (found) return found;
      await sleep(250);
    }
    return null;
  };
  const exactHeader = () => {
    const header = document.querySelector("#main header");
    if (!header) return false;
    const titled = [...header.querySelectorAll("[title]")]
      .filter((node) => node.getAttribute("title") === contact && node.textContent.trim() === contact);
    if (titled.length === 1) return true;
    const named = header.querySelector('[data-testid="conversation-info-header-chat-title"]');
    return named?.textContent.trim() === contact;
  };
  const composer = () => {
    const candidates = [...document.querySelectorAll('#main [data-testid="conversation-compose-box-input"], #main [role="textbox"][contenteditable="true"]')]
      .filter((node) => node.getAttribute("contenteditable") === "true"
        && ["Type a message", "Type a message to " + contact].includes(node.getAttribute("aria-label")));
    return candidates.length === 1 ? candidates[0] : null;
  };
  const outgoing = () => {
    const records = new Map();
    for (const node of document.querySelectorAll("#main .message-out[data-id]")) {
      const textNode = node.querySelector('[data-testid="selectable-text"]');
      const text = (textNode?.innerText || textNode?.textContent || "").trim();
      if (!text) continue;
      records.set(node.getAttribute("data-id"), {
        id: node.getAttribute("data-id"), text,
        sent: !!node.querySelector('[data-icon="msg-check"], [data-icon="msg-dblcheck"]'),
        pending: !!node.querySelector('[data-icon="msg-time"]'),
      });
    }
    for (const message of document.querySelectorAll('#main [data-testid="msg-container"]')) {
      if (!message.querySelector('[data-icon="tail-out"]')) continue;
      const node = message.closest("[data-id]");
      const id = node?.getAttribute("data-id");
      const textNode = message.querySelector('[data-testid="selectable-text"]');
      const text = textNode?.innerText || textNode?.textContent;
      if (!id || !text) continue;
      const label = (node.querySelector('[data-testid="msg-meta"] [aria-label]')?.getAttribute("aria-label") || "").trim().toLowerCase();
      const previous = records.get(id);
      records.set(id, { id, text: text.trim(), sent: previous?.sent || ["sent", "delivered", "read"].includes(label),
        pending: previous?.pending || ["pending", "sending", "waiting"].includes(label) });
    }
    return [...records.values()];
  };
  const setEditable = (element, text) => {
    element.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(element);
    selection.removeAllRanges();
    selection.addRange(range);
    if (!document.execCommand("insertText", false, text)) {
      element.textContent = text;
      element.dispatchEvent(new InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
    }
  };

  if (!await waitFor(() => document.querySelector("#pane-side"), 16000)) return fail("AUTHENTICATION_ERROR");
  if (!exactHeader()) {
    const search = [...document.querySelectorAll('[role="textbox"]')].find((node) =>
      ["Search input textbox", "Search or start a new chat"].includes(node.getAttribute("aria-label")));
    if (!search) return fail("AUTHORIZATION_ERROR");
    if (search instanceof HTMLInputElement) {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter.call(search, contact);
      search.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (search.getAttribute("contenteditable") === "true") {
      setEditable(search, contact);
    } else return fail("AUTHORIZATION_ERROR");
    const candidate = await waitFor(() => {
      const matches = [...document.querySelectorAll("#pane-side [title]")]
        .filter((node) => node.getAttribute("title") === contact);
      return matches.length === 1 ? matches[0] : null;
    }, 7000);
    if (!candidate) return fail("AUTHORIZATION_ERROR");
    const row = candidate.closest('[role="row"]');
    if (!row) return fail("AUTHORIZATION_ERROR");
    row.scrollIntoView({ block: "center" });
    const box = row.getBoundingClientRect();
    return { ok: false, error_code: "CLICK_REQUIRED", click: { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) } };
  }
  if (!composer()) return fail("AUTHORIZATION_ERROR");

  if (operation === "check") return { ok: true, result: { verified: true } };
  if (operation === "read") {
    const items = [...document.querySelectorAll('#main [data-testid="msg-container"]')].slice(-25).map((node) => {
      const text = node.querySelector('[data-testid="selectable-text"]')?.textContent?.trim();
      const message = node.closest("[data-id]");
      const outgoingMessage = !!node.querySelector('[data-icon="tail-out"]');
      const status = message?.querySelector('[data-testid="msg-meta"] [aria-label]')?.getAttribute("aria-label")?.trim() || "";
      return text && message ? { id: message.getAttribute("data-id"), content: text.slice(0, 4000), outgoing: outgoingMessage, status: status.slice(0, 30) } : null;
    }).filter(Boolean);
    return { ok: true, result: { application: "whatsapp", title: contact, items } };
  }
  if (operation === "verify") {
    if (typeof payload.id !== "string" || typeof payload.body !== "string") return fail("VERIFICATION_ERROR");
    const confirmed = await waitFor(() => outgoing().some((item) =>
      item.id === payload.id && item.text === payload.body && item.sent && !item.pending), 8000);
    return { ok: true, result: { verified: !!confirmed, provider_id: payload.id } };
  }
  if (operation === "confirm_send") {
    if (!Array.isArray(payload.before) || typeof payload.body !== "string") return fail("VERIFICATION_ERROR", true);
    const before = new Set(payload.before);
    const match = await waitFor(() => {
      const matches = outgoing().filter((item) => !before.has(item.id) && item.text === payload.body);
      return matches.length === 1 ? matches[0] : null;
    }, 12000);
    if (!match) return fail("VERIFICATION_ERROR", true);
    return { ok: true, result: { id: match.id, contact, body: payload.body, idempotency_key: payload.idempotency_key } };
  }
  const body = payload.body;
  if (typeof body !== "string" || !body.trim() || body.length > 4000 || !payload.idempotency_key) return fail("AUTHORIZATION_ERROR");
  const input = composer();
  if (input.textContent.trim()) return fail("CONFLICT_DETECTED");
  const before = outgoing().map((item) => item.id);
  setEditable(input, body);
  const sendButton = await waitFor(() => {
    const matches = [...document.querySelectorAll("#main button, #main [role=button]")]
      .filter((node) => node.getAttribute("aria-label") === "Send");
    return matches.length === 1 ? matches[0] : null;
  }, 2500);
  if (!sendButton) return fail("BROWSER_AUTOMATION_ERROR");
  const box = sendButton.getBoundingClientRect();
  return { ok: false, error_code: "SEND_CLICK_REQUIRED", before,
    click: { x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2) } };
}

async function runWhatsAppJob(contents, job) {
  let attempted = false;
  try {
    let answer;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      answer = await contents.executeJavaScript(`(${inWhatsAppPage.toString()})(${JSON.stringify(job)})`);
      if (answer?.error_code !== "CLICK_REQUIRED") break;
      const { x, y } = answer.click || {};
      if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0) {
        return { ok: false, error_code: "AUTHORIZATION_ERROR", attempted: false };
      }
      contents.sendInputEvent({ type: "mouseMove", x, y });
      contents.sendInputEvent({ type: "mouseDown", x, y, button: "left", clickCount: 1 });
      contents.sendInputEvent({ type: "mouseUp", x, y, button: "left", clickCount: 1 });
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (answer?.error_code === "CLICK_REQUIRED") {
      return { ok: false, error_code: "AUTHORIZATION_ERROR", attempted: false };
    }
    if (answer?.error_code !== "SEND_CLICK_REQUIRED") return answer;
    const { x, y } = answer.click || {};
    if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0) {
      return { ok: false, error_code: "BROWSER_AUTOMATION_ERROR", attempted: false };
    }
    attempted = true;
    contents.sendInputEvent({ type: "mouseMove", x, y });
    contents.sendInputEvent({ type: "mouseDown", x, y, button: "left", clickCount: 1 });
    contents.sendInputEvent({ type: "mouseUp", x, y, button: "left", clickCount: 1 });
    const confirmation = { operation: "confirm_send", payload: { ...job.payload, before: answer.before } };
    return await contents.executeJavaScript(`(${inWhatsAppPage.toString()})(${JSON.stringify(confirmation)})`);
  } catch {
    return { ok: false, error_code: "BROWSER_AUTOMATION_ERROR", attempted };
  }
}

module.exports = { inWhatsAppPage, runWhatsAppJob };
