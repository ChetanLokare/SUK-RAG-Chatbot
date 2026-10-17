import request from "./client";

/* ===============================
   FILE UPLOADS
=============================== */

export function uploadCSV(formData) {
  return request("/admin/upload/csv", {
    method: "POST",
    headers: {}, // ❗ important → browser sets multipart
    body: formData
  });
}

export function uploadPDF(formData) {
  return request("/admin/upload/pdf", {
    method: "POST",
    headers: {},
    body: formData
  });
}

export function uploadZIP(formData) {
  return request("/admin/upload/zip", {
    method: "POST",
    headers: {},
    body: formData
  });
}

/* ===============================
   URL UPLOAD
=============================== */

export function uploadURL(payload) {
  return request("/admin/upload/url", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
