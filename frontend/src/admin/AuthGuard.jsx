import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { API } from "../api/config";
import { authHeaders, clearSession, getToken } from "./api/auth";

export default function AuthGuard({ children }) {
  const location = useLocation();

  const [isChecking, setIsChecking] = useState(true);
  const [isLogged, setIsLogged] = useState(false);

  useEffect(() => {
    let cancelled = false;

    // Ask the server whether the stored token is actually valid
    // (not expired, signed with the current secret).
    const verify = async () => {
      if (!getToken()) {
        return false;
      }

      try {
        const res = await fetch(`${API}/admin/auth/me`, {
          headers: authHeaders(),
        });

        if (res.ok) return true;

        if (res.status === 401) clearSession();
        return false;
      } catch (err) {
        console.error("AuthGuard error:", err);
        return false;
      }
    };

    verify().then((ok) => {
      if (cancelled) return;
      setIsLogged(ok);
      setIsChecking(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  if (isChecking) {
    return null;
  }

  if (!isLogged) {
    return (
      <Navigate
        to="/admin/login"
        replace
        state={{ from: location }}
      />
    );
  }

  return children;
}
