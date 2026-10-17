import { useEffect, useState } from "react";
import SourceActions from "./SourceActions";

import {
  bulkApprove,
  bulkDelete,
  bulkIngest,
  bulkReingest,
  bulkUpdateCategory
} from "../api/sources";

import { API } from "../../api/config";
import { authHeaders, handleUnauthorized } from "../api/auth";
import { CATEGORIES } from "../constants/categories";

export default function SourceTable() {
  const [sources, setSources] = useState([]);
  const [selected, setSelected] = useState([]);

  const [categoryFilter, setCategoryFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [bulkCategory, setBulkCategory] = useState("");
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 🔥 PAGINATION
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;

  // ======================================================
  // FETCH
  // ======================================================

  const fetchSources = async () => {
    setError("");

    try {
      const params = new URLSearchParams();

      if (categoryFilter !== "all")
        params.append("category", categoryFilter);

      if (typeFilter !== "all")
        params.append("type", typeFilter); // 🔥 FIXED

      if (statusFilter !== "all")
        params.append("status", statusFilter);

      const res = await fetch(`${API}/admin/sources?${params.toString()}`, {
        headers: authHeaders()
      });

      if (res.status === 401) {
        handleUnauthorized();
        return;
      }

      if (!res.ok) throw new Error("Failed to fetch");

      const data = await res.json();

      setSources(Array.isArray(data) ? data : []);
      setSelected([]);
      setPage(1); // 🔥 reset page on filter

    } catch (err) {
      console.error(err);
      setError("Failed to load sources.");
    }
  };

  useEffect(() => {
    fetchSources();
  }, [categoryFilter, typeFilter, statusFilter]);

  // ======================================================
  // PAGINATION LOGIC
  // ======================================================

  const totalPages = Math.ceil(sources.length / PAGE_SIZE);

  const paginatedSources = sources.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE
  );

  // ======================================================
  // SELECTION
  // ======================================================

  const toggle = id => {
    setSelected(prev =>
      prev.includes(id)
        ? prev.filter(x => x !== id)
        : [...prev, id]
    );
  };

  const selectAll = () => {
    setSelected(paginatedSources.map(s => s.id));
  };

  const clearSelection = () => {
    setSelected([]);
    setBulkCategory("");
  };

  const allSelected =
    paginatedSources.length > 0 &&
    paginatedSources.every(s => selected.includes(s.id));

  // ======================================================
  // SAFE BULK
  // ======================================================

  const safeBulk = async (fn, expectJson = false) => {
    if (loading || selected.length === 0) return;

    setLoading(true);
    setError("");
    setProgress(null);

    try {
      const res = await fn();

      if (!res || !res.ok) {
        const text = res ? await res.text() : "";
        throw new Error(text || "Bulk request failed");
      }

      if (expectJson) {
        const data = await res.json();
        setProgress(data);
      }

      await fetchSources();
      clearSelection();

    } catch (err) {
      console.error(err);
      setError(err.message || "Bulk failed");
    }

    setLoading(false);
  };

  // ======================================================
  // BULK ACTIONS
  // ======================================================

  const approveSelected = () => safeBulk(() => bulkApprove(selected));
  const ingestSelected = () => safeBulk(() => bulkIngest(selected), true);
  const reingestSelected = () => safeBulk(() => bulkReingest(selected), true);

  const updateCategorySelected = () => {
    if (!bulkCategory) return;
    safeBulk(() => bulkUpdateCategory(selected, bulkCategory));
  };

  const deleteSelected = () => {
    if (!window.confirm(`Delete ${selected.length} sources?`)) return;
    safeBulk(() => bulkDelete(selected));
  };

  // ======================================================
  // RENDER
  // ======================================================

  return (
    <>
      {error && <div className="error-box">{error}</div>}

      {/* FILTERS */}
      <div className="filter-bar">
        <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
          <option value="all">All Categories</option>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>

        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="all">All Types</option>
          <option value="url">URL</option>
          <option value="pdf">PDF</option>
          <option value="csv">CSV</option>
          <option value="zip">ZIP</option>
        </select>

        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="ingested">Ingested</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* BULK */}
      {selected.length > 0 && (
        <div className="bulk-bar">
          <button disabled={loading} onClick={approveSelected}>
            Approve ({selected.length})
          </button>
          <button disabled={loading} onClick={ingestSelected}>Ingest</button>
          <button disabled={loading} onClick={reingestSelected}>Re-ingest</button>

          <select value={bulkCategory} onChange={e => setBulkCategory(e.target.value)}>
            <option value="">Change category</option>
            {CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>

          <button disabled={!bulkCategory || loading} onClick={updateCategorySelected}>
            Apply
          </button>

          <button className="danger" disabled={loading} onClick={deleteSelected}>
            Delete
          </button>
        </div>
      )}

      {/* TABLE */}
      <table className="admin-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => allSelected ? clearSelection() : selectAll()}
              />
            </th>
            <th>Type</th>
            <th>Status</th>
            <th>Category</th>
            <th>Source</th>
            <th>Error</th>
            <th>Actions</th>
          </tr>
        </thead>

        <tbody>
          {paginatedSources.map(s => (
            <tr key={s.id}>
              <td>
                <input
                  type="checkbox"
                  checked={selected.includes(s.id)}
                  onChange={() => toggle(s.id)}
                />
              </td>
              <td>{s.source_type}</td>
              <td className={`status-${s.status}`}>{s.status}</td>
              <td>{s.category}</td>
              <td className="source-value">{s.source_value}</td>
              <td className="status-failed">
                {s.status === "failed" && s.error_message}
              </td>
              <td>
                <SourceActions source={s} refresh={fetchSources} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* 🔥 PAGINATION CONTROLS */}
      <div className="pagination">
        <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>
          Prev
        </button>

        <span>Page {page} / {totalPages || 1}</span>

        <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>
          Next
        </button>
      </div>
    </>
  );
}