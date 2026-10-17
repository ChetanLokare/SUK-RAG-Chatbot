import { useEffect, useState } from "react";
import { deleteVector, getVectorStats, rebuildVector } from "../api/vector";

export default function VectorPanel() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadStats = async () => {
    try {
      setError("");
      const data = await getVectorStats();
      setStats(data);
    } catch (err) {
      console.error("Vector stats error:", err);
      setError("Failed to load vector database stats.");
    }
  };

  const handleRebuild = async () => {
    try {
      setLoading(true);
      setError("");
      await rebuildVector();
      await loadStats();
    } catch (err) {
      console.error("Rebuild error:", err);
      setError("Vector rebuild failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    const confirmDelete = window.confirm(
      "Are you sure you want to delete the entire vector database?"
    );

    if (!confirmDelete) return;

    try {
      setLoading(true);
      setError("");
      await deleteVector();
      await loadStats();
    } catch (err) {
      console.error("Delete error:", err);
      setError("Vector deletion failed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  return (
    <div style={{ marginTop: 20 }}>
      <h3>Vector Database</h3>

      {error && (
        <p style={{ color: "red", marginBottom: 10 }}>
          {error}
        </p>
      )}

      {stats ? (
        <div>
          <p><strong>Documents:</strong> {stats.documents ?? 0}</p>
          {stats.collections && (
            <p><strong>Collections:</strong> {stats.collections}</p>
          )}
        </div>
      ) : (
        <p>Loading stats...</p>
      )}

      <div style={{ marginTop: 10 }}>
        <button
          onClick={handleRebuild}
          disabled={loading}
          style={{ marginRight: 8 }}
        >
          {loading ? "Processing..." : "Rebuild"}
        </button>

        <button
          onClick={handleDelete}
          disabled={loading}
        >
          {loading ? "Processing..." : "Delete"}
        </button>
      </div>
    </div>
  );
}
