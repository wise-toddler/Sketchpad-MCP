import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/context/AuthContext";

// Handles the #session_id=... fragment returned by Emergent Google Auth.
export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const sessionId = match ? decodeURIComponent(match[1]) : null;

    const run = async () => {
      if (!sessionId) {
        navigate("/", { replace: true });
        return;
      }
      try {
        const res = await apiClient.post("/auth/session", { session_id: sessionId });
        setUser(res.data.user);
        window.history.replaceState(null, "", "/dashboard");
        navigate("/dashboard", { replace: true, state: { user: res.data.user } });
      } catch (e) {
        navigate("/", { replace: true });
      }
    };
    run();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center blueprint-grid" data-testid="auth-callback">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-muted-foreground font-mono text-sm">Establishing secure session…</p>
      </div>
    </div>
  );
}
