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

module.exports = { isAllowedNavigation, isExternalGoogleAuthorization };
