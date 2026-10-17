/*
  Central API client
  ✔ Uses .env base URL
  ✔ Handles JSON + FormData
  ✔ Handles empty responses
  ✔ Injects admin token
  ✔ Auto logout on 401
*/

const BASE = import.meta.env.VITE_API_URL;

/**
 * Generic request helper
 */
async function request(path, options = {}) {
  if (!BASE) {
    throw new Error("VITE_API_URL is not defined in .env");
  }

  // Ensure leading slash
  const safePath = path.startsWith("/") ? path : `/${path}`;

  const isFormData = options.body instanceof FormData;

  // -----------------------------
  // HEADERS
  // -----------------------------
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {})
  };

  // Inject token automatically
  try {
    const token = localStorage.getItem("admin_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } catch {}

  // -----------------------------
  // REQUEST
  // -----------------------------
  const res = await fetch(`${BASE}${safePath}`, {
    ...options,
    headers,
    credentials: "include"
  });

  // -----------------------------
  // ⭐ AUTO LOGOUT ON 401
  // -----------------------------
  if (res.status === 401) {
    try {
      localStorage.removeItem("admin_token");
      localStorage.removeItem("admin_logged_in");
    } catch {}

    // Notify AdminApp safely
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("admin:logout"));
    }

    throw new Error("Unauthorized");
  }

  // -----------------------------
  // ERROR HANDLING
  // -----------------------------
  if (!res.ok) {
    let message = "API request failed";

    try {
      const text = await res.text();
      if (text) message = text;
    } catch {}

    throw new Error(message);
  }

  // -----------------------------
  // SAFE RESPONSE PARSING
  // -----------------------------
  const contentType = res.headers.get("content-type");

  if (contentType && contentType.includes("application/json")) {
    return res.json();
  }

  const text = await res.text();
  if (!text) return {};

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export default request;
