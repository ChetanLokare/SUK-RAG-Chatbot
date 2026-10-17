import { Navigate, Route, Routes } from "react-router-dom";

import AuthGuard from "./src/admin/AuthGuard";
import AdminDashboard from "./src/admin/page/AdminDashboard";
import Login from "./src/admin/page/Login";
import UserApp from "./src/user/UserApp";

export default function AppRouter() {
  return (
    <Routes>

      {/* ================= USER ================= */}
      <Route path="/" element={<UserApp />} />

      {/* ================= ADMIN LOGIN ================= */}
      <Route path="/admin/login" element={<Login />} />

      {/* ================= ADMIN PROTECTED ================= */}
      <Route
        path="/admin"
        element={
          <AuthGuard>
            <AdminDashboard />
          </AuthGuard>
        }
      />

      {/* ================= REMOVE THIS (IMPORTANT FIX) ================= */}
      {/* ❌ DO NOT REDIRECT /admin/* → /admin (causes bypass/conflicts) */}

      {/* ================= FALLBACK ================= */}
      <Route path="*" element={<Navigate to="/" replace />} />

    </Routes>
  );
}