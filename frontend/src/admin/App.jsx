import { useEffect } from "react";

export default function AdminApp({ children }) {

  // ✅ global auto logout (401)
  useEffect(() => {
    const handler = () => {
      console.warn("⚠️ Auto logout triggered");

      try {
        localStorage.removeItem("admin_token");
        localStorage.removeItem("admin_logged_in");
      } catch {}

      window.location.href = "/admin/login";
    };

    window.addEventListener("admin:logout", handler);

    return () => {
      window.removeEventListener("admin:logout", handler);
    };
  }, []);

  return <>{children}</>;
}