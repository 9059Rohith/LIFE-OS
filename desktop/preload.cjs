const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lifeosDesktop", Object.freeze({
  select: (name) => ipcRenderer.send("lifeos:select", name),
  setViewport: (bounds) => ipcRenderer.send("lifeos:viewport", bounds),
  reloadWorkspace: () => ipcRenderer.send("lifeos:reload-workspace"),
  reload: (name) => ipcRenderer.send("lifeos:reload", name),
  onStatus: (handler) => {
    if (typeof handler !== "function") return () => {};
    const listener = (_event, status) => handler(status);
    ipcRenderer.on("lifeos:status", listener);
    return () => ipcRenderer.removeListener("lifeos:status", listener);
  },
}));
