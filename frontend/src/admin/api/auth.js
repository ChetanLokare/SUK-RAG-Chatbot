/*
  Shared helpers for admin authentication.
  The token is stored by Login.jsx after a successful login.
*/

export function getToken() {
  try {
    return localStorage.getItem("admin_token");
  } catch {
    return null;
  }
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function clearSession() {
  try {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_logged_in");
  } catch {}
}

// Call when the server answers 401 (missing/expired/invalid token).
// AdminApp listens for this event and sends the user to the login page.
export function handleUnauthorized() {
  clearSession();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("admin:logout"));
  }
}
