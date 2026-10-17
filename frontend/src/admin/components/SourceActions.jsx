import { useState } from "react";
import {
  bulkApprove,
  bulkDelete,
  bulkIngest
} from "../api/sources";

export default function SourceActions({ source, refresh }) {

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // =====================================================
  // SAFE ACTION WRAPPER (🔥 FULLY FIXED)
  // =====================================================

  const safeAction = async (actionFn) => {

    if (loading) return;

    setLoading(true);
    setError("");

    try {

      const res = await actionFn();

      // ❌ No response
      if (!res) {
        throw new Error("No response from server");
      }

      // ❌ Failed response
      if (!res.ok) {
        let message = "Request failed";

        try {
          const text = await res.text();
          if (text) message = text;
        } catch (_) {}

        throw new Error(message);
      }

      // ✅ Success → refresh table
      await refresh();

    } catch (err) {

      console.error("❌ Source action failed:", err);

      setError(
        err?.message ||
        "Operation failed. Please try again."
      );

    } finally {
      setLoading(false);
    }
  };


  // =====================================================
  // ACTIONS
  // =====================================================

  const approve = () =>
    safeAction(() => bulkApprove([source.id]));

  const ingest = () =>
    safeAction(() => bulkIngest([source.id]));

  const remove = () => {

    const confirmed = window.confirm(
      `Delete this source permanently?\n\n` +
      `This will remove:\n` +
      `• Source registry entry\n` +
      `• Stored file (if exists)\n` +
      `• Vector DB entries\n\n` +
      `This action CANNOT be undone.`
    );

    if (!confirmed) return;

    safeAction(() => bulkDelete([source.id]));
  };


  // =====================================================
  // RENDER
  // =====================================================

  return (
    <div className="source-actions">

      {/* ERROR */}
      {error && (
        <div className="error-text">
          {error}
        </div>
      )}

      {/* APPROVE */}
      {source.status === "pending" && (
        <button
          disabled={loading}
          onClick={approve}
        >
          {loading ? "Processing..." : "Approve"}
        </button>
      )}

      {/* INGEST */}
      {["approved", "failed"].includes(source.status) && (
        <button
          disabled={loading}
          onClick={ingest}
        >
          {loading ? "Processing..." : "Ingest"}
        </button>
      )}

      {/* DELETE */}
      {source.status !== "disabled" && (
        <button
          disabled={loading}
          className="danger"
          onClick={remove}
        >
          {loading ? "Processing..." : "Delete"}
        </button>
      )}

    </div>
  );
}