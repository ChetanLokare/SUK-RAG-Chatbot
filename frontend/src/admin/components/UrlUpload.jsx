import { useState } from "react";
import { uploadURL } from "../api/uploads";

export default function UrlUpload({ refresh }) {
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleAdd = async () => {
    setError("");
    setSuccess("");

    if (!url.trim()) {
      setError("URL is required.");
      return;
    }

    setLoading(true);

    try {
      await uploadURL({
        url,
        category: category || "general"
      });

      setSuccess("URL added.");
      setUrl("");
      setCategory("");

      if (refresh) await refresh();
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to add URL");
    }

    setLoading(false);
  };

  return (
    <div style={{ marginBottom: 20 }}>
      <h4>Add URL</h4>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>{success}</p>}

      <input
        placeholder="URL"
        value={url}
        onChange={e => setUrl(e.target.value)}
        style={{ width: 350 }}
      />

      <input
        placeholder="Category"
        value={category}
        onChange={e => setCategory(e.target.value)}
        style={{ marginLeft: 10 }}
      />

      <button
        onClick={handleAdd}
        disabled={loading}
        style={{ marginLeft: 10 }}
      >
        {loading ? "Adding..." : "Add URL"}
      </button>
    </div>
  );
}
