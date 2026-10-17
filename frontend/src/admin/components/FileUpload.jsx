import { useRef, useState } from "react";
import { uploadCSV, uploadPDF, uploadZIP } from "../api/uploads";

export default function FileUpload({ type, refresh }) {
  const inputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const getUploader = () => {
    if (type === "csv") return uploadCSV;
    if (type === "pdf") return uploadPDF;
    if (type === "zip") return uploadZIP;
    throw new Error("Unsupported upload type");
  };

  const handleUpload = async () => {
    setError("");
    setSuccess("");

    if (!file) {
      setError("Please select a file.");
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      if (category) {
        formData.append("category", category);
      }

      const uploader = getUploader();
      await uploader(formData);

      setSuccess("Upload successful.");
      setFile(null);
      setCategory("");

      // reset input
      if (inputRef.current) inputRef.current.value = "";

      if (refresh) await refresh();
    } catch (err) {
      console.error(err);
      setError(err.message || "Upload failed.");
    }

    setLoading(false);
  };

  return (
    <div style={{ marginBottom: 20 }}>
      <h4>Upload {type.toUpperCase()}</h4>

      {error && <p style={{ color: "red" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>{success}</p>}

      <input
        ref={inputRef}
        type="file"
        accept={`.${type}`}
        onChange={e => setFile(e.target.files?.[0] || null)}
      />

      <input
        placeholder="Category (optional)"
        value={category}
        onChange={e => setCategory(e.target.value)}
        style={{ marginLeft: 10 }}
      />

      <button
        onClick={handleUpload}
        disabled={loading}
        style={{ marginLeft: 10 }}
      >
        {loading ? "Uploading..." : `Upload ${type.toUpperCase()}`}
      </button>
    </div>
  );
}
