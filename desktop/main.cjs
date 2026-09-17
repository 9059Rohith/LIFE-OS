const path = require("node:path");
const { app, BaseWindow, WebContentsView, ipcMain, session, shell: systemShell } = require("electron");
const { hostedWorkspaceOrigin, workspaceAddress, isAllowedNavigation, isExternalGoogleAuthorization } = require("./navigation.cjs");
const { startDesktopBridge } = require("./desktop-bridge.cjs");

app.enableSandbox();

const shellUrl = workspaceAddress(process.env.LIFEOS_DESKTOP_URL || `${hostedWorkspaceOrigin}/desktop.html`);
const workspaceUrl = new URL("/", shellUrl);
const providers = Object.freeze({
  discord: { url: "https://discord.com/app", origin: "https://discord.com", partition: "persist:lifeos-discord" },
  whatsapp: { url: "https://web.whatsapp.com/", origin: "https://web.whatsapp.com", partition: "persist:lifeos-whatsapp" },
});

let window;
let shell;
let active = "none";
let offline = false;
let shellLoading = false;
let closing = false;
let connectionTimer;
let stopBridge;
let stage = { x: 180, y: 112, width: 760, height: 650 };
const views = new Map();
const viewStates = new Map();
const viewLoads = new Map();

function sendStatus(name, state, detail = "") {
  viewStates.set(name, { state, detail });
  if (!shell || shell.webContents.isDestroyed()) return;
  shell.webContents.send("lifeos:status", { name, state, detail });
}

function secureView(name, view) {
  const contents = view.webContents;
  contents.setWindowOpenHandler(() => ({ action: "deny" }));
  contents.on("will-navigate", (event, url) => {
    if (name === "lifeos" && isExternalGoogleAuthorization(url)) {
      event.preventDefault();
      void systemShell.openExternal(url).catch(() => sendStatus("lifeos", "error", "Could not open the system browser for Google authorization."));
      return;
    }
    if (!isAllowedNavigation(name, url, shellUrl.origin, providers)) event.preventDefault();
  });
  contents.on("did-start-loading", () => sendStatus(name, "loading"));
  contents.on("did-finish-load", () => sendStatus(name, "ready"));
  contents.on("did-fail-load", (_event, code, description, url, isMainFrame) => {
    if (isMainFrame && code !== -3) sendStatus(name, "error", `${description} (${code})`);
  });
  contents.on("render-process-gone", () => sendStatus(name, "error", "The app view stopped responding. Use Reload page to try again."));
}

function configureSession(partition) {
  const selected = session.fromPartition(partition);
  selected.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  selected.setPermissionCheckHandler(() => false);
  return selected;
}

function createView(name) {
  const partition = name === "lifeos" ? "persist:lifeos-workspace" : providers[name].partition;
  configureSession(partition);
  const view = new WebContentsView({
    webPreferences: {
      partition,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  });
  if (name === "whatsapp") {
    // WhatsApp's browser gate rejects Electron's extra product token even when
    // the bundled Chromium is new enough. Keep Chromium's actual version.
    const chromiumAgent = view.webContents.getUserAgent().replace(/\s(?:Electron|lifeos-desktop)\/[\d.]+/gi, "");
    view.webContents.setUserAgent(chromiumAgent);
  }
  secureView(name, view);
  views.set(name, view);
  return view;
}

function ensureView(name) {
  let view = views.get(name);
  if (!view) {
    view = createView(name);
    const url = name === "lifeos" ? workspaceUrl.href : providers[name].url;
    sendStatus(name, "loading");
    viewLoads.set(name, view.webContents.loadURL(url).catch((error) => {
      sendStatus(name, "error", error.message);
      return null;
    }));
  }
  return view;
}

function setActive(name) {
  if (!window || !["none", "lifeos", "discord", "whatsapp"].includes(name)) return;
  if (active === name && (name === "none" || views.has(name))) return;
  if (active !== "none") {
    const previous = views.get(active);
    if (previous) window.contentView.removeChildView(previous);
  }
  active = name;
  if (name === "none") return;
  const newlyCreated = !views.has(name);
  const view = ensureView(name);
  view.setBounds(stage);
  window.contentView.addChildView(view);
  if (!newlyCreated) {
    const last = viewStates.get(name);
    sendStatus(name, view.webContents.isLoading() ? "loading" : last?.state || "ready", last?.detail || "");
  }
}

function boundedViewport(value) {
  if (!window || !value || typeof value !== "object") return null;
  const bounds = {};
  for (const key of ["x", "y", "width", "height"]) {
    const number = Number(value[key]);
    if (!Number.isFinite(number)) return null;
    bounds[key] = Math.round(number);
  }
  const size = window.getContentBounds();
  if (bounds.x < 0 || bounds.y < 0 || bounds.width < 200 || bounds.height < 180
    || bounds.x + bounds.width > size.width + 2 || bounds.y + bounds.height > size.height + 2) return null;
  return bounds;
}

function fromShell(event) {
  return shell && event.sender === shell.webContents && event.senderFrame === shell.webContents.mainFrame;
}

async function loadShell() {
  if (!shell || shell.webContents.isDestroyed() || shellLoading) return;
  shellLoading = true;
  try {
    await shell.webContents.loadURL(shellUrl.href);
    offline = false;
  } catch {
    offline = true;
    if (shell && !shell.webContents.isDestroyed()) {
      await shell.webContents.loadFile(path.join(__dirname, "offline.html"));
    }
  } finally {
    shellLoading = false;
  }
}

app.whenReady().then(() => {
  const shellPartition = "persist:lifeos-workspace";
  configureSession(shellPartition);
  window = new BaseWindow({ width: 1512, height: 940, minWidth: 1060, minHeight: 660,
    title: "LIFEOS", backgroundColor: "#f7faf7", autoHideMenuBar: true });
  shell = new WebContentsView({ webPreferences: {
    partition: shellPartition,
    preload: path.join(__dirname, "preload.cjs"),
    nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true,
  } });
  secureView("shell", shell);
  window.contentView.addChildView(shell);
  const resize = () => {
    const size = window.getContentBounds();
    shell.setBounds({ x: 0, y: 0, width: size.width, height: size.height });
  };
  resize();
  window.on("resize", resize);
  window.on("close", (event) => {
    if (closing) return;
    event.preventDefault();
    closing = true;
    const sessions = ["persist:lifeos-workspace", "persist:lifeos-discord", "persist:lifeos-whatsapp"]
      .map((partition) => session.fromPartition(partition));
    void Promise.allSettled(sessions.map((selected) => selected.cookies.flushStore()))
      .finally(() => {
        for (const selected of sessions) selected.flushStorageData();
        if (window && !window.isDestroyed()) window.destroy();
      });
  });
  window.on("closed", () => {
    stopBridge?.();
    if (connectionTimer) clearInterval(connectionTimer);
    for (const view of views.values()) view.webContents.close();
    shell.webContents.close();
    views.clear();
    viewStates.clear();
    viewLoads.clear();
    window = undefined;
    shell = undefined;
  });
  void loadShell();
  stopBridge = startDesktopBridge(shellUrl.origin, session.fromPartition(shellPartition), async () => {
    setActive("whatsapp");
    shell.webContents.send("lifeos:focus-provider", "whatsapp");
    const view = ensureView("whatsapp");
    await viewLoads.get("whatsapp");
    if (!view.webContents.getURL().startsWith(providers.whatsapp.origin + "/")) {
      throw new Error("WhatsApp view is unavailable");
    }
    return view;
  });
  connectionTimer = setInterval(async () => {
    if (!offline || shellLoading) return;
    try {
      const timeout = shellUrl.protocol === "https:" ? 10000 : 2000;
      const response = await fetch(new URL("/health", shellUrl), { signal: AbortSignal.timeout(timeout) });
      if (response.ok) await loadShell();
    } catch { /* The offline screen stays visible until the backend is ready. */ }
  }, 5000);
  window.show();

  ipcMain.on("lifeos:select", (event, name) => { if (fromShell(event)) setActive(name); });
  ipcMain.on("lifeos:viewport", (event, value) => {
    if (!fromShell(event)) return;
    const next = boundedViewport(value);
    if (!next) return;
    stage = next;
    const view = views.get(active);
    if (view) view.setBounds(stage);
  });
  ipcMain.on("lifeos:reload-workspace", (event) => {
    if (!fromShell(event)) return;
    const view = views.get("lifeos");
    if (view) view.webContents.reload();
  });
  ipcMain.on("lifeos:reload", (event, name) => {
    if (!fromShell(event) || name !== active) return;
    const view = views.get(name);
    if (view) {
      sendStatus(name, "loading");
      view.webContents.reload();
    }
  });
});

app.on("window-all-closed", () => app.quit());
