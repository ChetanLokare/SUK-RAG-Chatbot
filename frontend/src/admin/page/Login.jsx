import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "../../api/config";
import "../admin.css";

export default function Login({ onLogin }) {
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // =====================================================
  // LOGIN FUNCTION
  // =====================================================

  const login = async () => {
    if (loading) return;

    const u = username.trim();
    const p = password.trim();

    if (!u || !p) {
      setError("Username and password are required.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      let res;

      try {
        res = await fetch(`${API}/admin/auth/login`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username: u,
            password: p,
          }),
        });
      } catch (networkErr) {
        throw new Error("Unable to connect to server.");
      }

      // -----------------------------
      // HANDLE BAD RESPONSE
      // -----------------------------
      if (!res.ok) {
        let message = "Invalid username or password.";

        try {
          const body = await res.json();
          if (typeof body?.detail === "string") message = body.detail;
        } catch {}

        throw new Error(message);
      }

      // -----------------------------
      // SAFE JSON PARSE
      // -----------------------------
      let data = {};
      try {
        data = await res.json();
      } catch {
        data = {};
      }

      if (!data?.token) {
        throw new Error("Invalid username or password.");
      }

      // =================================================
      // STORE AUTH (SIMPLIFIED + CONSISTENT)
      // =================================================

      const token = data.token;

      try {
        localStorage.setItem("admin_token", token);
        localStorage.removeItem("admin_logged_in");
      } catch (storageErr) {
        console.error("Storage error:", storageErr);
      }

      // optional callback
      if (onLogin) {
        onLogin(token);
      }

      // =================================================
      // REDIRECT (MATCH ROUTER)
      // =================================================

      navigate("/admin", { replace: true });

    } catch (err) {
      console.error("❌ Login error:", err);

      setError(
        err?.message ||
        "Login failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  // =====================================================
  // ENTER KEY SUPPORT
  // =====================================================

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      login();
    }
  };

  // =====================================================
  // RENDER
  // =====================================================

  return (
    <div className="admin-login-wrapper">
      <div className="admin-login-card">

        <h2 className="admin-login-title">
          SUK RAG – Admin Login
        </h2>

        {error && (
          <div className="admin-login-error">
            {error}
          </div>
        )}

        <input
          className="admin-login-input"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />

        <input
          className="admin-login-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />

        <button
          className="admin-login-button"
          onClick={login}
          disabled={loading}
        >
          {loading ? "Logging in..." : "Login"}
        </button>

        <p className="admin-login-hint">
      
        </p>

      </div>
    </div>
  );
}