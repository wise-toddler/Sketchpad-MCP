import { PenTool, Zap, Bot, Lock, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { startLogin } from "@/lib/authRedirect";

export default function Login() {
  const handleGoogleLogin = () => startLogin();

  const features = [
    { icon: Bot, title: "AI-Native Canvas", desc: "MCP agents draw, connect and iterate on live diagrams." },
    { icon: Zap, title: "Realtime Sync", desc: "WebSocket streaming — watch shapes appear as they draw." },
    { icon: Lock, title: "Per-User Isolation", desc: "Every canvas is scoped and secured to your account." },
    { icon: GitBranch, title: "excalidraw.com Export", desc: "One-click shareable, editable diagram links." },
  ];

  return (
    <div className="min-h-screen blueprint-grid flex flex-col lg:flex-row" data-testid="login-container">
      {/* Left / hero */}
      <div className="lg:w-1/2 flex flex-col justify-center px-8 sm:px-16 py-16 fade-up">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-11 h-11 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/30">
            <PenTool className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="font-heading font-bold text-xl tracking-tight">Excalidraw MCP Cloud</span>
        </div>

        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-4">
          Hardened · Self-Hostable · Multi-User
        </p>
        <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.05] mb-6">
          The canvas your<br />AI agents draw on.
        </h1>
        <p className="text-muted-foreground text-base max-w-md mb-10 leading-relaxed">
          Give Claude Code, Cursor or any MCP client a live Excalidraw surface — with
          Google auth, durable per-user projects, and real-time sync you can watch in the browser.
        </p>

        <Button
          data-testid="google-login-btn"
          onClick={handleGoogleLogin}
          className="w-full sm:w-auto h-12 px-8 text-base rounded-full font-semibold shadow-lg shadow-primary/30 hover:shadow-primary/50 transition-shadow"
        >
          <svg className="w-5 h-5 mr-1" viewBox="0 0 24 24"><path fill="currentColor" d="M12.24 10.29v3.7h5.19c-.23 1.34-1.6 3.93-5.19 3.93-3.12 0-5.67-2.58-5.67-5.77s2.55-5.77 5.67-5.77c1.78 0 2.97.76 3.65 1.41l2.49-2.4C16.9 3.6 14.78 2.6 12.24 2.6 7.3 2.6 3.3 6.6 3.3 11.55s4 8.95 8.94 8.95c5.16 0 8.58-3.63 8.58-8.74 0-.59-.06-1.04-.14-1.48H12.24z"/></svg>
          Continue with Google
        </Button>
        <p className="text-xs text-muted-foreground mt-4 font-mono">
          Secure OAuth · no passwords stored
        </p>
      </div>

      {/* Right / feature panel */}
      <div className="lg:w-1/2 glass-panel border-l border-border/60 flex items-center px-8 sm:px-16 py-16">
        <div className="grid sm:grid-cols-2 gap-5 w-full max-w-xl fade-up">
          {features.map((f, i) => (
            <div
              key={f.title}
              data-testid="auth-hero-feature-card"
              className="rounded-2xl border border-border/70 bg-card/60 p-6 hover:border-primary/50 transition-colors"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="w-10 h-10 rounded-lg bg-primary/15 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-heading font-semibold text-lg mb-1">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
