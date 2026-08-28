import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus, PenTool, LogOut, MoreVertical, Trash2, Pencil, Layers, Bot, Search, Users,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/context/AuthContext";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });
  const [creating, setCreating] = useState(false);

  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  const load = async () => {
    try {
      const res = await apiClient.get("/projects");
      setProjects(res.data);
    } catch (e) {
      toast.error("Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const createProject = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      const res = await apiClient.post("/projects", form);
      setCreateOpen(false);
      setForm({ name: "", description: "" });
      toast.success("Canvas created");
      navigate(`/canvas/${res.data.project_id}`);
    } catch (e) {
      toast.error("Failed to create canvas");
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = async (p) => {
    try {
      await apiClient.delete(`/projects/${p.project_id}`);
      setProjects((prev) => prev.filter((x) => x.project_id !== p.project_id));
      toast.success("Canvas deleted");
    } catch (e) {
      toast.error("Failed to delete");
    }
  };

  const submitRename = async () => {
    if (!renameValue.trim() || !renameTarget) return;
    try {
      const res = await apiClient.patch(`/projects/${renameTarget.project_id}`, { name: renameValue });
      setProjects((prev) => prev.map((x) => (x.project_id === renameTarget.project_id ? res.data : x)));
      setRenameTarget(null);
      toast.success("Renamed");
    } catch (e) {
      toast.error("Failed to rename");
    }
  };

  const filtered = projects.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()));
  const owned = filtered.filter((p) => p.is_owner);
  const shared = filtered.filter((p) => !p.is_owner);

  return (
    <div className="min-h-screen blueprint-grid" data-testid="dashboard-container">
      {/* Header */}
      <header className="glass-panel border-b border-border/60 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/30">
              <PenTool className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="font-heading font-bold text-lg tracking-tight hidden sm:block">Excalidraw MCP Cloud</span>
          </div>
          <div className="flex items-center gap-3">
            {user?.picture && (
              <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full border border-border" />
            )}
            <span className="text-sm text-muted-foreground hidden sm:block">{user?.name}</span>
            <ThemeToggle />
            <button
              onClick={logout}
              data-testid="logout-btn"
              className="w-9 h-9 rounded-lg hover:bg-accent flex items-center justify-center text-muted-foreground hover:text-foreground"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8 fade-up">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-2">Your Workspace</p>
            <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight">Canvas Projects</h1>
            <p className="text-muted-foreground mt-1">{projects.length} canvas{projects.length !== 1 ? "es" : ""} · isolated & persistent</p>
          </div>
          <Button
            data-testid="create-project-btn"
            onClick={() => setCreateOpen(true)}
            className="h-11 px-6 rounded-full font-semibold shadow-lg shadow-primary/30"
          >
            <Plus className="w-4 h-4 mr-1" /> New Canvas
          </Button>
        </div>

        <div className="relative mb-8 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="search-projects-input"
            placeholder="Search canvases…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9 bg-card/60"
          />
        </div>

        {loading ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-52 rounded-2xl bg-card/40 border border-border/50 animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24 fade-up" data-testid="empty-state">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-5">
              <Layers className="w-8 h-8 text-primary" />
            </div>
            <h3 className="font-heading text-xl font-semibold mb-2">
              {query ? "No matching canvases" : "No canvases yet"}
            </h3>
            <p className="text-muted-foreground mb-6">Create your first canvas and connect an AI agent to it.</p>
            {!query && (
              <Button onClick={() => setCreateOpen(true)} className="rounded-full px-6">
                <Plus className="w-4 h-4 mr-1" /> Create Canvas
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-10">
            {owned.length > 0 && (
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {owned.map((p, i) => (
                  <ProjectCard key={p.project_id} p={p} i={i}
                    onOpen={() => navigate(`/canvas/${p.project_id}`)}
                    onRename={() => { setRenameTarget(p); setRenameValue(p.name); }}
                    onDelete={() => deleteProject(p)} />
                ))}
              </div>
            )}
            {shared.length > 0 && (
              <div data-testid="shared-with-me-section">
                <div className="flex items-center gap-2 mb-4">
                  <Users className="w-4 h-4 text-muted-foreground" />
                  <h2 className="font-heading font-semibold text-lg">Shared with me</h2>
                  <span className="text-sm text-muted-foreground">({shared.length})</span>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {shared.map((p, i) => (
                    <ProjectCard key={p.project_id} p={p} i={i}
                      onOpen={() => navigate(`/canvas/${p.project_id}`)} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent data-testid="create-project-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Create new canvas</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Name</label>
              <Input
                data-testid="project-name-input"
                autoFocus
                placeholder="System Architecture"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && createProject()}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Description <span className="text-muted-foreground">(optional)</span></label>
              <Textarea
                data-testid="project-description-input"
                placeholder="What will you diagram here?"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button data-testid="submit-create-project-btn" onClick={createProject} disabled={creating || !form.name.trim()}>
              {creating ? "Creating…" : "Create Canvas"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename dialog */}
      <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <DialogContent data-testid="rename-project-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Rename canvas</DialogTitle>
          </DialogHeader>
          <Input
            data-testid="rename-input"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitRename()}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)}>Cancel</Button>
            <Button data-testid="submit-rename-btn" onClick={submitRename}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function RoleBadge({ role }) {
  if (!role || role === "owner") return null;
  const label = role === "editor" ? "Editor" : "Viewer";
  return (
    <Badge
      data-testid="role-badge"
      variant="secondary"
      className="font-mono text-[10px] uppercase tracking-wider"
    >
      {label}
    </Badge>
  );
}

function ProjectCard({ p, i, onOpen, onRename, onDelete }) {
  const isOwner = p.is_owner;
  return (
    <div
      data-testid="project-card-item"
      className="group rounded-2xl border border-border/70 bg-card/60 overflow-hidden hover:border-primary/50 transition-all fade-up cursor-pointer"
      style={{ animationDelay: `${i * 50}ms` }}
      onClick={onOpen}
    >
      <div className="h-32 relative blueprint-grid border-b border-border/60 flex items-center justify-center">
        {isOwner && (
          <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  data-testid="project-menu-trigger"
                  className="w-8 h-8 rounded-lg glass-panel border border-border/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem data-testid="rename-project-btn" onClick={onRename}>
                  <Pencil className="w-4 h-4 mr-2" /> Rename
                </DropdownMenuItem>
                <DropdownMenuItem
                  data-testid="delete-project-btn"
                  className="text-destructive focus:text-destructive"
                  onClick={onDelete}
                >
                  <Trash2 className="w-4 h-4 mr-2" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
        {!isOwner && (
          <div className="absolute top-3 right-3 z-10">
            <RoleBadge role={p.role} />
          </div>
        )}
        <PenTool className="w-10 h-10 text-primary/40 group-hover:text-primary/70 transition-colors" />
      </div>
      <div className="p-4">
        <h3 className="font-heading font-semibold text-base truncate">{p.name}</h3>
        <p className="text-sm text-muted-foreground truncate mt-0.5 min-h-[1.25rem]">
          {p.description || "No description"}
        </p>
        <div className="flex items-center gap-3 mt-3">
          <span className="font-mono text-[11px] text-muted-foreground flex items-center gap-1">
            <Layers className="w-3 h-3" /> {p.element_count} elements
          </span>
          {isOwner && (
            <span className="font-mono text-[11px] text-emerald-400/80 flex items-center gap-1">
              <Bot className="w-3 h-3" /> MCP ready
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
