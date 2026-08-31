import { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";
import { toast } from "sonner";

const TABS = [
  {
    id: "claude",
    label: "Claude Desktop",
    file: "claude_desktop_config.json",
    lang: "json",
    code: `{
  "mcpServers": {
    "sketchpad": {
      "command": "npx",
      "args": ["-y", "mcp-remote",
        "https://your-app.com/api/engine/<AGENT_TOKEN>/mcp"]
    }
  }
}`,
  },
  {
    id: "cursor",
    label: "Cursor",
    file: ".cursor/mcp.json",
    lang: "json",
    code: `{
  "mcpServers": {
    "sketchpad": {
      "url": "https://your-app.com/api/engine/<AGENT_TOKEN>/mcp"
    }
  }
}`,
  },
  {
    id: "npx",
    label: "Quickstart",
    file: "terminal",
    lang: "bash",
    code: `# clone + run all three services locally
git clone https://github.com/wise-toddler/Sketchpad-MCP && cd Sketchpad-MCP
cp backend/.env.example backend/.env   # set MONGO_URL + secret
docker compose up   # frontend + gateway + engine + mongo`,
  },
];

export default function McpCodeTabs() {
  const [active, setActive] = useState("claude");
  const [copied, setCopied] = useState(false);
  const tab = TABS.find((t) => t.id === active);

  const copy = () => {
    navigator.clipboard.writeText(tab.code);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="sketch-card overflow-hidden" data-testid="mcp-snippet-tabs">
      <div className="flex items-center gap-1 border-b border-border/60 bg-muted/40 px-2 pt-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`mcp-tab-${t.id}`}
            onClick={() => setActive(t.id)}
            className={`rounded-t-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              active === t.id
                ? "bg-background text-foreground border border-b-0 border-border/60"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={copy}
          data-testid="mcp-copy-btn"
          className="ml-auto mb-1 flex items-center gap-1.5 rounded-md border border-border/60 px-2 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="flex items-center gap-2 px-4 pt-2.5 pb-1 font-mono text-[11px] text-muted-foreground">
        <Terminal className="w-3.5 h-3.5" /> {tab.file}
      </div>
      <pre className="overflow-x-auto px-4 pb-4 pt-1 font-mono text-[12px] leading-relaxed text-foreground">
        <code>{tab.code}</code>
      </pre>
    </div>
  );
}
