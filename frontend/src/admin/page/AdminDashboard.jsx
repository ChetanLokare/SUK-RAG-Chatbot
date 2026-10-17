import "../admin.css";


import SourceTable from "../components/SourceTable";
import UploadPanel from "../components/UploadPanel";
import VectorPanel from "../components/VectorPanel";

export default function AdminDashboard() {
  return (
    <div className="admin-container">
      <h2 className="admin-title">
        SUK RAG – Admin Dashboard
      </h2>

      <div className="admin-panel">
        <UploadPanel />
      </div>

      <div className="admin-panel">
        <SourceTable />
      </div>

      <div className="admin-panel vector-panel">
        <VectorPanel />
      </div>
    </div>
  );
}
