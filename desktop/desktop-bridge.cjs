"use strict";

const { runWhatsAppJob } = require("./whatsapp-bridge.cjs");

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function startDesktopBridge(workspaceOrigin, workspaceSession, ensureWhatsApp) {
  let stopped = false;
  let currentRequest;
  const address = (path) => new URL(path, workspaceOrigin).href;
  const request = (path, options = {}) => {
    currentRequest = new AbortController();
    return workspaceSession.fetch(address(path), {
      credentials: "include",
      signal: currentRequest.signal,
      ...options,
    });
  };
  const loop = async () => {
    while (!stopped) {
      try {
        const sessionResponse = await request("/api/session");
        if (!sessionResponse.ok) {
          await pause(4000);
          continue;
        }
        const workspace = await sessionResponse.json();
        if (workspace.mode !== "live" || !workspace.csrf_token) {
          await pause(4000);
          continue;
        }
        const response = await request("/api/desktop/bridge/next", {
          method: "POST",
          headers: { "X-CSRF-Token": workspace.csrf_token, Origin: workspaceOrigin },
        });
        if (!response.ok) {
          await pause(response.status === 404 ? 10000 : 4000);
          continue;
        }
        const { job } = await response.json();
        if (!job || stopped) continue;
        let answer = { ok: false, error_code: "BROWSER_AUTOMATION_ERROR", attempted: false };
        if (typeof job.id === "string" && ["check", "read", "send", "verify"].includes(job.operation)) {
          try {
            const view = await ensureWhatsApp();
            answer = await runWhatsAppJob(view.webContents, job);
          } catch {
            answer.attempted = job.operation === "send";
          }
        }
        await request("/api/desktop/bridge/result", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": workspace.csrf_token, Origin: workspaceOrigin },
          body: JSON.stringify({ id: job.id, ...answer }),
        });
      } catch {
        if (!stopped) await pause(4000);
      }
    }
  };
  void loop();
  return () => {
    stopped = true;
    currentRequest?.abort();
  };
}

module.exports = { startDesktopBridge };
