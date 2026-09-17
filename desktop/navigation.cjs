const hostedWorkspaceOrigin = "https://lifeos-live-production.up.railway.app";

function workspaceAddress(value) {
  const parsed = new URL(value);
  if (parsed.pathname !== "/desktop.html" || parsed.search || parsed.hash) {
    throw new Error("The LIFEOS desktop URL must point to /desktop.html without query parameters.");
  }
  const local = parsed.protocol === "http:" && ["127.0.0.1", "localhost"].includes(parsed.hostname);
  if (!local && parsed.origin !== hostedWorkspaceOrigin) {
    throw new Error("The LIFEOS desktop URL must use the trusted hosted workspace or local loopback.");
  }
  return parsed;
}

function isAllowedNavigation(name, url, shellOrigin, providers) {
  try {
    const origin = new URL(url).origin;
    if (name === "shell") return origin === shellOrigin;
    if (name === "lifeos") return origin === shellOrigin;
    return Object.hasOwn(providers, name) && origin === providers[name].origin;
  } catch {
    return false;
  }
}

function isExternalGoogleAuthorization(url) {
  try {
    const parsed = new URL(url);
    return parsed.origin === "https://accounts.google.com" && parsed.pathname === "/o/oauth2/v2/auth";
  } catch {
    return false;
  }
}

module.exports = { hostedWorkspaceOrigin, workspaceAddress, isAllowedNavigation, isExternalGoogleAuthorization };
