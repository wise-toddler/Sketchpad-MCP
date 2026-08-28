import { useEffect, useState } from "react";
import { Globe, Link2, Building2, Copy, Check, Trash2, Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";

const ROLE_OPTS = [
  { v: "viewer", l: "Viewer" },
  { v: "editor", l: "Editor" },
];
const ACCESS_OPTS = [{ v: "none", l: "Off" }, ...ROLE_OPTS];

export default function ShareDialog({ projectId, open, onClose }) {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [copied, setCopied] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.get(`/projects/${projectId}/share`);
      setState(r.data);
    } catch (e) {
      toast.error("Couldn't load sharing settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (open) load(); /* eslint-disable-next-line */ }, [open]);

  const patch = async (payload) => {
    try {
      const r = await apiClient.put(`/projects/${projectId}/share`, payload);
      setState(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Update failed");
    }
  };

  const invite = async () => {
    if (!email.trim()) return;
    try {
      const r = await apiClient.post(`/projects/${projectId}/members`, { email: email.trim(), role: inviteRole });
      setState(r.data);
      setEmail("");
      toast.success("Invited");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Invite failed");
    }
  };

  const changeMember = async (m, role) => {
    const r = await apiClient.patch(`/projects/${projectId}/members`, { email: m.email, role });
    setState(r.data);
  };
  const removeMember = async (m) => {
    const r = await apiClient.delete(`/projects/${projectId}/members`, { params: { email: m.email } });
    setState(r.data);
  };

  const linkUrl = state ? `${window.location.origin}/canvas/${projectId}?share=${state.share_token}` : "";
  const copyLink = () => {
    navigator.clipboard.writeText(linkUrl);
    setCopied(true);
    toast.success("Link copied");
    setTimeout(() => setCopied(false), 1500);
  };
  const rotateLink = async () => {
    const r = await apiClient.post(`/projects/${projectId}/share/rotate-link`);
    setState((s) => ({ ...s, share_token: r.data.share_token }));
    toast.success("Link reset — old links no longer work");
  };

  const RoleSelect = ({ value, onChange, options = ROLE_OPTS, testid }) => (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-32 text-sm" data-testid={testid}><SelectValue /></SelectTrigger>
      <SelectContent>
        {options.map((o) => <SelectItem key={o.v} value={o.v}>{o.l}</SelectItem>)}
      </SelectContent>
    </Select>
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="share-dialog" className="max-w-lg">
        <DialogHeader><DialogTitle className="font-heading">Share canvas</DialogTitle></DialogHeader>

        {loading || !state ? (
          <div className="py-10 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : (
          <div className="space-y-6">
            {/* Invite by email */}
            <div>
              <div className="flex gap-2">
                <Input
                  data-testid="invite-email-input"
                  placeholder="Invite by email…"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && invite()}
                />
                <RoleSelect value={inviteRole} onChange={setInviteRole} testid="invite-role-select" />
                <Button data-testid="invite-submit-btn" onClick={invite}><UserPlus className="w-4 h-4" /></Button>
              </div>
              {state.members.length > 0 && (
                <div className="mt-3 space-y-2" data-testid="members-list">
                  {state.members.map((m) => (
                    <div key={m.email} className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center text-xs font-semibold text-primary uppercase">
                        {m.email[0]}
                      </div>
                      <span className="text-sm flex-1 truncate">{m.email}</span>
                      <RoleSelect value={m.role} onChange={(r) => changeMember(m, r)} />
                      <button onClick={() => removeMember(m)} data-testid="member-remove-btn" className="text-muted-foreground hover:text-destructive p-1">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* General access */}
            <div className="space-y-3">
              <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">General access</p>

              <div className="flex items-center gap-3 rounded-lg border border-border p-3">
                <Link2 className="w-5 h-5 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">Anyone with the link</div>
                  <div className="text-xs text-muted-foreground">Viewers can open anonymously; editing needs sign-in</div>
                </div>
                <RoleSelect
                  value={state.link_access}
                  onChange={(v) => patch({ link_access: v })}
                  options={ACCESS_OPTS}
                  testid="link-access-select"
                />
              </div>

              {state.link_access !== "none" && (
                <div className="flex items-center gap-2 pl-1">
                  <Input readOnly value={linkUrl} data-testid="share-link-input" className="text-xs font-mono" />
                  <Button variant="outline" size="sm" onClick={copyLink} data-testid="copy-share-link-btn">
                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={rotateLink} data-testid="rotate-link-btn">Reset</Button>
                </div>
              )}

              <div className="flex items-center gap-3 rounded-lg border border-border p-3">
                <Building2 className="w-5 h-5 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">
                    Everyone at {state.workspace_domain || "your workspace"}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {state.workspace_available
                      ? `Any signed-in @${state.workspace_domain} teammate`
                      : "Not available for personal email domains"}
                  </div>
                </div>
                <RoleSelect
                  value={state.workspace_access}
                  onChange={(v) => patch({ workspace_access: v })}
                  options={ACCESS_OPTS}
                  testid="workspace-access-select"
                />
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
