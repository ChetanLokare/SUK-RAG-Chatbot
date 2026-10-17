import { API } from "../../api/config";
import { authHeaders, handleUnauthorized } from "./auth";

/* ============================================================
   CORE FETCH (RAW RESPONSE)
============================================================ */

async function rawRequest(path, options = {}) {
  try {
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(options.headers || {})
      }
    });

    if (res.status === 401) {
      handleUnauthorized();
    }

    return res;

  } catch (err) {
    console.error("❌ Network error:", err);
    throw new Error("Network error. Please check backend.");
  }
}


/* ============================================================
   SAFE JSON PARSER
============================================================ */

async function parseJSON(res) {
  try {
    const text = await res.text();
    return text ? JSON.parse(text) : {};
  } catch (err) {
    console.error("❌ JSON parse error:", err);
    return {};
  }
}


/* ============================================================
   JSON REQUEST (AUTO PARSE)
============================================================ */

async function request(path, options = {}) {
  const res = await rawRequest(path, options);

  if (!res || !res.ok) {
    const text = res ? await res.text() : "";
    throw new Error(text || "API request failed");
  }

  return parseJSON(res);
}


/* ============================================================
   FETCH SOURCES
============================================================ */

export async function fetchSources(query = "") {
  return request(`/admin/sources${query}`);
}


/* ============================================================
   SINGLE SOURCE ACTIONS
============================================================ */

export function updateSourceStatus(id, status) {
  return request(`/admin/sources/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function ingestSource(id) {
  return rawRequest(`/admin/sources/${id}/ingest`, {
    method: "POST"
  });
}

export function updateCategory(id, category) {
  return request(`/admin/sources/${id}/category`, {
    method: "PATCH",
    body: JSON.stringify({ category })
  });
}


/* ============================================================
   BULK OPERATIONS (🔥 RETURN RAW RESPONSE)
============================================================ */

export function bulkApprove(ids) {
  return rawRequest(`/admin/sources/bulk/approve`, {
    method: "POST",
    body: JSON.stringify({ source_ids: ids })
  });
}

export function bulkIngest(ids) {
  return rawRequest(`/admin/sources/bulk/ingest`, {
    method: "POST",
    body: JSON.stringify({ source_ids: ids })
  });
}

export function bulkReingest(ids) {
  return rawRequest(`/admin/sources/bulk/reingest`, {
    method: "POST",
    body: JSON.stringify({ source_ids: ids })
  });
}

export function bulkUpdateCategory(ids, category) {
  return rawRequest(`/admin/sources/bulk/category`, {
    method: "POST",
    body: JSON.stringify({
      source_ids: ids,
      category
    })
  });
}

export function bulkDelete(ids) {
  return rawRequest(`/admin/sources/bulk/delete`, {
    method: "POST",
    body: JSON.stringify({ source_ids: ids })
  });
}