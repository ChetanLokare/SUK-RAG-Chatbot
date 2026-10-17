import request from "./client";

/**
 * Get vector database statistics
 * Backend: GET /admin/vector/stats
 */
export function getVectorStats() {
  return request("/admin/vector/stats");
}

/**
 * Rebuild entire vector database
 * Backend: POST /admin/vector/rebuild
 */
export function rebuildVector() {
  return request("/admin/vector/rebuild", {
    method: "POST"
  });
}

/**
 * Delete entire vector database
 * Backend: DELETE /admin/vector/delete
 */
export function deleteVector() {
  return request("/admin/vector/delete", {
    method: "DELETE"
  });
}
