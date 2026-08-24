import { useState } from "react";
import { X, Copy, Check, RefreshCw, Sparkles, Terminal, Bot } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/apiClient";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function McpAgentConnectPanel({ project, open, onClose, onProjectUpdate, onSimulate }) {
  const [copied, setCopied] = useState("");
  const [rotating, setRotating] = useState(false);
  const [simulating, setSimulating] = useState(false);

  const endpoint = `${BACKEND_URL}/api/engine/${project.agent_token}`;
  const claudeConfig = JSON.stringify(
    {
      mcpServers: {
        excalidraw: {
          command: "npx",
          args: ["-y", "mcp-excalidraw-server"],
          env: {
            EXPRESS_SERVER_URL: endpoint,
            ENABLE_CANVAS_SYNC: "true",
            CANVAS_ID: "default",
          },
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
      const res = await apiClient.post(`/projects/${project.project_id}/rotate-token`);
      onProjectUpdate({ ...project, agent_token: res.data.agent_token });
      toast.success("Agent token rotated");
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

  const Field = ({ label, value, copyKey, mono = true }) => (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
        <button
          onClick={() => copy(value, copyKey)}
          data-testid={`copy-${copyKey}-btn`}
          className="text-primary hover:text-primary/80 transition-colors"
        >
          {copied === copyKey ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
      <div className={`rounded-lg border border-border bg-background/60 p-3 text-xs break-all ${mono ? "font-mono" : ""} text-foreground/90`}>
        {value}
      </div>
    </div>
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
          <p className="text-sm text-muted-foreground leading-relaxed">
            Point Claude Code, Cursor, or any MCP client at this project. All calls are scoped to
            this canvas via the token below — the gateway enforces isolation server-side.
          </p>

          <button
            onClick={simulate}
            disabled={simulating}
            data-testid="simulate-ai-draw-btn"
            className="w-full rounded-xl border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors px-4 py-3.5 flex items-center gap-3 text-left disabled:opacity-60"
          >
            <Sparkles className={`w-5 h-5 text-emerald-400 ${simulating ? "animate-spin" : ""}`} />
            <div>
              <div className="font-semibold text-sm text-emerald-300">Simulate AI Draw</div>
              <div className="text-xs text-emerald-400/70">Watch a diagram appear live — no external agent needed</div>
            </div>
          </button>

          <div data-testid="mcp-token-display">
            <Field label="Agent Token" value={project.agent_token} copyKey="mcp-token" />
          </div>
          <Field label="MCP Endpoint URL" value={endpoint} copyKey="mcp-endpoint" />

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" /> claude_desktop_config.json
              </span>
              <button
                onClick={() => copy(claudeConfig, "mcp-config")}
                data-testid="copy-mcp-config-btn"
                className="text-primary hover:text-primary/80"
              >
                {copied === "mcp-config" ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <pre className="rounded-lg border border-border bg-background/60 p-3 text-[11px] font-mono overflow-x-auto text-foreground/90" data-testid="mcp-live-logs-terminal">
{claudeConfig}
            </pre>
          </div>

          <Button
            variant="outline"
            onClick={rotate}
            disabled={rotating}
            data-testid="rotate-token-btn"
            className="w-full"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${rotating ? "animate-spin" : ""}`} />
            Rotate Token
          </Button>
        </div>
      </div>
    </div>
  );
}
