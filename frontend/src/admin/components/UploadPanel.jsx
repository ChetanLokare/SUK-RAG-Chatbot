import FileUpload from "./FileUpload";
import UrlUpload from "./UrlUpload"; // ⭐ CRITICAL FIX

export default function UploadPanel({ refresh }) {
  return (
    <div>
      <h3>Add Sources</h3>

      {/* URL upload */}
      <UrlUpload refresh={refresh} />

      {/* File uploads */}
      <FileUpload type="csv" refresh={refresh} />
      <FileUpload type="pdf" refresh={refresh} />
      <FileUpload type="zip" refresh={refresh} />

      <hr />
    </div>
  );
}
