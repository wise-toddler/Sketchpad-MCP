import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import AuthCallback from "@/components/auth/AuthCallback";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import CanvasPage from "@/pages/CanvasPage";

const FullLoader = () => (
  <div className="min-h-screen flex items-center justify-center blueprint-grid">
    <Loader2 className="w-8 h-8 animate-spin text-primary" />
  </div>
);

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <FullLoader />;
  if (!user) return <Navigate to="/" replace />;
  return children;
}

function RootRoute() {
  const { user, loading } = useAuth();
  if (loading) return <FullLoader />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Login />;
}

function CanvasGuard() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const hasShare = new URLSearchParams(location.search).get("share");
  if (loading) return <FullLoader />;
  if (!user && !hasShare) return <Navigate to="/" replace />;
  return <CanvasPage />;
}

function AppRouter() {
  const location = useLocation();
  // Process OAuth callback fragment FIRST (synchronously) to avoid race conditions.
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/canvas/:projectId" element={<CanvasGuard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
        <Toaster theme="dark" position="top-right" richColors />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
