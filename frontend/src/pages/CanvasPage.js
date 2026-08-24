import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Download, ChevronDown, Bot, Loader2, ImageIcon, FileCode, FileJson } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";
import ExcalidrawCanvasView from "@/components/canvas/ExcalidrawCanvasView";
import McpAgentConnectPanel from "@/components/canvas/McpAgentConnectPanel";
import { exportPng, exportSvg, exportJson } from "@/lib/excalidrawExport";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export default function CanvasPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const apiRef = useRef(null);

  useEffect(() => {
    apiClient
      .get(`/projects/${projectId}`)
      .then((res) => setProject(res.data))
      .catch(() => {
        toast.error("Project not found");
        navigate("/dashboard");
      })
      .finally(() => setLoading(false));
  }, [projectId, navigate]);

  const runExport = async (fn, label) => {
    if (!apiRef.current) return;
    try {
      await fn(apiRef.current, project?.name || "canvas");
      toast.success(`Exported ${label}`);
    } catch (e) {
      toast.error(`Export failed`);
    }
  };

  const simulate = async () => {
    await apiClient.post(`/projects/${projectId}/simulate`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center blueprint-grid">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Top bar */}
      <header
        className="glass-panel border-b border-border/60 h-14 flex items-center justify-between px-4 z-30 shrink-0"
        data-testid="canvas-top-bar"
      >
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate("/dashboard")}
            data-testid="back-to-dashboard-btn"
            className="w-9 h-9 rounded-lg hover:bg-accent flex items-center justify-center shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <h1 className="font-heading font-semibold text-sm truncate">{project?.name}</h1>
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                {live && <span className="live-dot" />}
                <span className={`relative inline-flex rounded-full h-2 w-2 ${live ? "bg-emerald-400" : "bg-muted-foreground"}`} />
              </span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {live ? "Live · synced" : "Connecting…"}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                data-testid="canvas-export-dropdown"
                className="h-9 px-3 rounded-lg border border-border hover:bg-accent flex items-center gap-2 text-sm font-medium"
              >
                <Download className="w-4 h-4" /> Export <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem data-testid="export-png-btn" onClick={() => runExport(exportPng, "PNG")}>
                <ImageIcon className="w-4 h-4 mr-2" /> PNG image
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="export-svg-btn" onClick={() => runExport(exportSvg, "SVG")}>
                <FileCode className="w-4 h-4 mr-2" /> SVG vector
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="export-json-btn" onClick={() => runExport(exportJson, ".excalidraw")}>
                <FileJson className="w-4 h-4 mr-2" /> .excalidraw file
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <button
            onClick={() => setPanelOpen(true)}
            data-testid="mcp-panel-toggle-btn"
            className="h-9 px-3 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-2 text-sm font-semibold shadow-lg shadow-primary/25"
          >
            <Bot className="w-4 h-4" /> Connect Agent
          </button>
        </div>
      </header>

      {/* Canvas */}
      <div className="flex-1 relative">
        <ExcalidrawCanvasView projectId={projectId} apiRef={apiRef} onConnectionChange={setLive} />
      </div>

      {project && (
        <McpAgentConnectPanel
          project={project}
          open={panelOpen}
          onClose={() => setPanelOpen(false)}
          onProjectUpdate={setProject}
          onSimulate={simulate}
        />
      )}
    </div>
  );
}
