const KEY = "post_login_redirect";

// Kick off Emergent Google OAuth, optionally remembering where to land afterwards.
export function startLogin(returnTo) {
  try {
    if (returnTo) localStorage.setItem(KEY, returnTo);
    else localStorage.removeItem(KEY);
  } catch (_) { /* ignore */ }
  // DO NOT hardcode/alter this URL or add fallbacks — it breaks auth.
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

// Read + clear the remembered destination. Only internal paths are allowed.
export function consumePostLoginRedirect() {
  try {
    const v = localStorage.getItem(KEY);
    localStorage.removeItem(KEY);
    if (v && v.startsWith("/") && !v.startsWith("//")) return v;
  } catch (_) { /* ignore */ }
  return null;
}
