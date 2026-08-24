import { useState, useEffect } from "react";
import { X, Copy, Check, RefreshCw, Sparkles, Terminal, Bot, Layers, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/apiClient";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function McpAgentConnectPanel({ project, open, onClose, onSimulate }) {
  const [copied, setCopied] = useState("");
  const [rotating, setRotating] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [mcpToken, setMcpToken] = useState(null);

  useEffect(() => {
    if (!open) return;
    apiClient.get("/auth/mcp-token").then((r) => setMcpToken(r.data.mcp_token)).catch(() => {});
  }, [open]);

  const endpoint = mcpToken ? `${BACKEND_URL}/api/mcp/${mcpToken}` : "";
  const claudeConfig = JSON.stringify(
    {
      mcpServers: {
        excalidraw: {
          command: "npx",
          args: ["-y", "mcp-excalidraw-server"],
          env: { EXPRESS_SERVER_URL: endpoint, ENABLE_CANVAS_SYNC: "true" },
        },
      },
    },
    null,
    2
  );

  const copy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(""), 1500);
  };

  const rotate = async () => {
    setRotating(true);
    try {
      const res = await apiClient.post("/auth/mcp-token/rotate");
      setMcpToken(res.data.mcp_token);
      toast.success("MCP token rotated");
    } catch (e) {
      toast.error("Failed to rotate token");
    } finally {
      setRotating(false);
    }
  };

  const simulate = async () => {
    setSimulating(true);
    try {
      await onSimulate();
      toast.success("AI agent drew on the canvas");
    } catch (e) {
      toast.error("Simulation failed");
    } finally {
      setSimulating(false);
    }
  };

  if (!open) return null;

  const CopyBtn = ({ value, k }) => (
    <button onClick={() => copy(value, k)} data-testid={`copy-${k}-btn`} className="text-primary hover:text-primary/80 transition-colors">
      {copied === k ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );

  return (
    <div className="fixed inset-0 z-40 flex justify-end" data-testid="mcp-panel-container">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md h-full glass-panel border-l border-border/60 shadow-2xl overflow-y-auto fade-up">
        <div className="sticky top-0 glass-panel border-b border-border/60 px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
              <Bot className="w-4 h-4 text-emerald-400" />
            </div>
            <h2 className="font-heading font-semibold text-lg">Connect AI Agent</h2>
          </div>
          <button onClick={onClose} data-testid="mcp-panel-close-btn" className="text-muted-foreground hover:text-foreground">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
            <p className="text-xs font-mono uppercase tracking-wider text-primary mb-1">User-level connection</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              One token for your whole account. Your agent can <strong className="text-foreground">list, create, switch and delete</strong> canvases
              (<code className="font-mono text-xs text-primary">list_canvases</code>, <code className="font-mono text-xs text-primary">create_canvas</code>,
              {" "}<code className="font-mono text-xs text-primary">set_active_canvas</code>) and draw on any of them — all scoped to you.
            </p>
          </div>

          <button
            onClick={simulate}
            disabled={simulating}
            data-testid="simulate-ai-draw-btn"
            className="w-full rounded-xl border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors px-4 py-3.5 flex items-center gap-3 text-left disabled:opacity-60"
          >
            <Sparkles className={`w-5 h-5 text-emerald-400 ${simulating ? "animate-spin" : ""}`} />
            <div>
              <div className="font-semibold text-sm text-emerald-300">Simulate AI Draw</div>
              <div className="text-xs text-emerald-400/70">Watch a diagram appear live on this canvas — no external agent needed</div>
            </div>
          </button>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">MCP Endpoint (user-level)</span>
              {mcpToken && <CopyBtn value={endpoint} k="mcp-endpoint" />}
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3 text-xs break-all font-mono text-foreground/90" data-testid="mcp-token-display">
              {mcpToken ? endpoint : <span className="flex items-center gap-2 text-muted-foreground"><Loader2 className="w-3 h-3 animate-spin" /> loading…</span>}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/40 px-3 py-2.5 flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary shrink-0" />
            <div className="min-w-0">
              <div className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">This canvas id</div>
              <div className="text-xs font-mono truncate text-foreground/90">{project.project_id}</div>
            </div>
            <div className="ml-auto"><CopyBtn value={project.project_id} k="canvas-id" /></div>
          </div>
          <p className="text-xs text-muted-foreground -mt-3">
            Tip: ask your agent to <code className="font-mono text-primary">set_active_canvas</code> with the id above to draw here,
            or <code className="font-mono text-primary">create_canvas</code> to start a fresh one.
          </p>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" /> claude_desktop_config.json
              </span>
              {mcpToken && <CopyBtn value={claudeConfig} k="mcp-config" />}
            </div>
            <pre className="rounded-lg border border-border bg-background/60 p-3 text-[11px] font-mono overflow-x-auto text-foreground/90" data-testid="mcp-live-logs-terminal">
{claudeConfig}
            </pre>
          </div>

          <Button variant="outline" onClick={rotate} disabled={rotating || !mcpToken} data-testid="rotate-token-btn" className="w-full">
            <RefreshCw className={`w-4 h-4 mr-2 ${rotating ? "animate-spin" : ""}`} />
            Rotate MCP Token
          </Button>
        </div>
      </div>
    </div>
  );
}
