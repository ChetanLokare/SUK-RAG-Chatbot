import { useState } from "react";
import styles from "./ChatBox.module.css";

const API = "http://localhost:8000";

export default function CitationPanel({ citations = [], verified = false }) {
  const [open, setOpen] = useState(false);

  // Safety check
  if (!Array.isArray(citations) || citations.length === 0) {
    return null;
  }

  // Extract clean display name from path or URL
  const getDisplayName = (value) => {
    if (!value) return "Unknown Source";

    try {
      const parts = value.split("/");
      const lastPart = parts[parts.length - 1];

      return decodeURIComponent(lastPart);
    } catch {
      return value;
    }
  };

  const renderLink = (citation, index) => {
    if (!citation) return null;

    const { source_type, source_value, page_number } = citation;

    if (!source_value) return null;

    // PDF case (served by backend /pdf/{filename})
    if (source_type === "pdf") {
      const fileName = getDisplayName(source_value);

      return (
        <a
          key={index}
          href={`${API}/pdf/${fileName}`}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.citationLink}
        >
          📄 {fileName}
          {page_number && page_number > 0 ? ` (page ${page_number})` : ""}
        </a>
      );
    }

    // Default: URL case
    return (
      <a
        key={index}
        href={source_value}
        target="_blank"
        rel="noopener noreferrer"
        className={styles.citationLink}
      >
        🔗 {source_value}
      </a>
    );
  };

  return (
    <div className={styles.citationWrapper}>
      <button
        className={styles.citationToggle}
        onClick={() => setOpen(!open)}
      >
        📚 Sources{" "}
        <span
          className={
            verified ? styles.verifiedLabel : styles.unverifiedLabel
          }
        >
          {verified ? "(Verified)" : "(Unverified)"}
        </span>
        {open ? " ▲" : " ▼"}
      </button>

      {open && (
        <div className={styles.citationList}>
          {citations.map((c, i) => renderLink(c, i))}
        </div>
      )}
    </div>
  );
}
