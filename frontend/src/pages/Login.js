import {
  PenTool, Github, Bot, Users, Share2, Download, ServerCog, Zap, Star, ArrowRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { startLogin } from "@/lib/authRedirect";
import { ThemeToggle } from "@/components/ThemeToggle";
import SketchyCanvasMock from "@/components/landing/SketchyCanvasMock";
import McpCodeTabs from "@/components/landing/McpCodeTabs";
import { SketchUnderline, CurlyArrow } from "@/components/landing/HandDrawnBadges";

const GoogleIcon = ({ className = "w-5 h-5" }) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"/>
    <path fill="#EA4335" d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.4 14.97.5 12 .5A11 11 0 0 0 2.18 7.06L5.84 9.9C6.71 7.3 9.14 4.75 12 4.75z"/>
  </svg>
);

const GoogleButton = ({ testid, children = "Continue with Google" }) => (
  <button
    data-testid={testid}
    onClick={() => startLogin()}
    className="stamp-btn inline-flex items-center gap-2.5 px-6 py-3.5 text-base font-bold font-heading"
  >
    <span className="grid place-items-center w-6 h-6 rounded-full bg-white">
      <GoogleIcon className="w-4 h-4" />
    </span>
    {children}
    <ArrowRight className="w-4 h-4" />
  </button>
);

const FEATURES = [
  { id: "mcp-agent", span: "md:col-span-7", tag: "AGENT PROTOCOL", icon: Bot,
    title: "Agents draw, not just describe",
    desc: "Claude Code, Cursor, or any MCP client places rectangles, routes arrows and drops sticky notes with real Excalidraw coordinate math — then screenshots its own work to fix the layout.",
    note: "npx-friendly · scoped per-user token" },
  { id: "multiplayer", span: "md:col-span-5", tag: "WEBSOCKET ENGINE", icon: Zap,
    title: "Real-time multiplayer",
    desc: "Humans and agents share one canvas room with live presence cursors and last-writer-wins element sync.",
    note: "presence + live cursors" },
  { id: "notion-sharing", span: "md:col-span-4", tag: "COLLABORATION", icon: Share2,
    title: "Notion-style sharing",
    desc: "Invite by email, share view/edit links, or open a canvas to everyone in your workspace domain.",
    note: "invite · link · workspace" },
  { id: "export", span: "md:col-span-4", tag: "COMPATIBILITY", icon: Download,
    title: "Export everywhere",
    desc: "High-res PNG, SVG, and raw .excalidraw files you can commit next to your code.",
    note: "PNG · SVG · .excalidraw" },
  { id: "self-host", span: "md:col-span-4", tag: "SELF-HOSTING", icon: ServerCog,
    title: "Open-source & self-hostable",
    desc: "Three services + MongoDB. Run it on your own infra — your diagrams stay yours.",
    note: "MIT licensed" },
];

const AGENTS = ["Claude Code", "Cursor", "Windsurf", "Claude Desktop", "Codex CLI", "LangChain"];

export default function Login() {
  return (
    <div className="min-h-screen paper-grid text-foreground" data-testid="login-container">
      {/* Header */}
      <header className="sticky top-0 z-50 glass-panel border-b border-border/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#e11d48] dark:bg-[#f43f5e] border-[1.5px] border-foreground flex items-center justify-center" style={{ boxShadow: "2px 2px 0 var(--tw-shadow-color, currentColor)" }}>
              <PenTool className="w-5 h-5 text-white" />
            </div>
            <span className="font-heading font-extrabold text-lg tracking-tight">Sketchpad MCP</span>
            <span className="hidden sm:inline-block font-mono text-[10px] px-1.5 py-0.5 rounded border border-border text-muted-foreground">v0.9 · MCP</span>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-3">
            <a href="https://github.com/wise-toddler/Sketchpad-MCP" target="_blank" rel="noreferrer"
              className="hidden sm:flex items-center gap-1.5 rounded-lg border border-border px-3 h-9 text-sm font-medium hover:bg-accent transition-colors">
              <Github className="w-4 h-4" /> Star <Star className="w-3.5 h-3.5 fill-current text-amber-400" />
            </a>
            <ThemeToggle />
            <button
              data-testid="header-signin-btn"
              onClick={() => startLogin()}
              className="rounded-lg bg-foreground text-background px-4 h-9 text-sm font-semibold hover:opacity-90 transition-opacity"
            >
              Sign in
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-14 sm:pt-20 pb-16 grid lg:grid-cols-12 gap-10 lg:gap-8 items-center">
        <motion.div
          className="lg:col-span-7"
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        >
          <div className="inline-flex items-center gap-2 sticky-note bg-[#fde68a] dark:bg-[#4a3d12] px-3 py-1 mb-6 -rotate-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400 animate-pulse" />
            <span className="text-sm font-semibold text-[#5a3a0a] dark:text-[#fde68a] tracking-wide">MCP-NATIVE · MULTI-USER CO-CANVAS</span>
          </div>

          <h1 className="font-heading font-extrabold tracking-tight leading-[1.06] text-4xl sm:text-5xl lg:text-6xl">
            The Excalidraw canvas your{" "}
            <span className="relative whitespace-nowrap">
              <span className="marker mk-coral">AI agents draw</span>
              <SketchUnderline className="absolute -bottom-3 left-0 w-full h-4 text-[#e11d48] dark:text-[#f43f5e]" />
            </span>{" "}
            on — live.
          </h1>

          <p className="mt-7 text-base sm:text-lg text-muted-foreground max-w-xl leading-relaxed">
            Connect Claude Code, Cursor, or any MCP client straight to a collaborative whiteboard.
            Stream architecture diagrams and schemas while your team co-edits in the browser.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-5">
            <GoogleButton testid="google-login-btn" />
            <div className="relative">
              <CurlyArrow className="absolute -left-9 -top-6 w-8 h-8 text-muted-foreground/70 hidden sm:block" />
              <span className="font-hand text-xl text-muted-foreground">no API key to try it!</span>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-2.5">
            {[
              { icon: Zap, label: "Real-time sync" },
              { icon: Users, label: "Isolated workspaces" },
              { icon: Github, label: "100% open source" },
            ].map((s) => (
              <span key={s.label} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <s.icon className="w-3.5 h-3.5" /> {s.label}
              </span>
            ))}
          </div>
        </motion.div>

        <motion.div
          className="lg:col-span-5 relative"
          initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.55, delay: 0.15 }}
        >
          <div className="float-y">
            <SketchyCanvasMock />
          </div>
          <div className="sticky-note bg-[#a5f3fc] dark:bg-[#0c3a49] absolute -top-5 -right-2 px-3 py-1.5 rotate-3 text-[#0b3b47] dark:text-[#67e8f9] text-base hidden sm:block">
            Claude Code verified ✓
          </div>
          <div className="sticky-note bg-[#dcfce7] dark:bg-[#0d3320] absolute -bottom-4 -left-4 px-3 py-1.5 -rotate-2 text-[#14532d] dark:text-[#86efac] text-base hidden sm:block">
            per-user isolated
          </div>
        </motion.div>
      </section>

      {/* MCP developer section */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
        <div className="grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <p className="font-hand text-2xl text-[#e11d48] dark:text-[#f43f5e] mb-1">30-second setup</p>
            <h2 className="font-heading font-bold tracking-tight text-2xl sm:text-3xl lg:text-4xl mb-3">
              Drop it into Claude or Cursor
            </h2>
            <p className="text-muted-foreground leading-relaxed max-w-md">
              Sketchpad MCP speaks the standard Model Context Protocol. Paste one config block, hand your
              agent a scoped token, and it can list, create and draw on your canvases — nothing else.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Scoped per-user agent tokens", "Server-forced canvas isolation", "Works over stdio or HTTP"].map((t) => (
                <li key={t} className="flex items-center gap-2.5 text-muted-foreground">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#e11d48] dark:bg-[#f43f5e]" /> {t}
                </li>
              ))}
            </ul>
          </div>
          <McpCodeTabs />
        </div>
      </section>

      {/* Feature bento grid */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <h2 className="font-heading font-bold tracking-tight text-2xl sm:text-3xl lg:text-4xl mb-2">
          A whiteboard built for <span className="marker mk-cyan">humans + agents</span>
        </h2>
        <p className="text-muted-foreground mb-8">Everything you need to sketch, share and ship diagrams as living artifacts.</p>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-4" data-testid="feature-bento-grid">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.id}
              data-testid="auth-hero-feature-card"
              className={`sketch-card wobble-hover p-6 col-span-1 ${f.span}`}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.4, delay: (i % 3) * 0.06 }}
            >
              <div className="flex items-center gap-2 mb-4">
                <span className="grid place-items-center w-9 h-9 rounded-lg bg-[#e11d48]/10 dark:bg-[#f43f5e]/15 text-[#e11d48] dark:text-[#f43f5e]">
                  <f.icon className="w-5 h-5" />
                </span>
                <span className="font-mono text-[10px] tracking-widest text-muted-foreground">{f.tag}</span>
              </div>
              <h3 className="font-heading font-bold text-xl mb-1.5">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              <p className="mt-4 font-hand text-lg text-[#e11d48] dark:text-[#f43f5e]">{f.note}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Social proof */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
        <p className="text-center font-hand text-2xl text-muted-foreground mb-6">plays nicely with your stack</p>
        <div className="flex flex-wrap justify-center gap-3">
          {AGENTS.map((a) => (
            <span key={a} className="rounded-full border border-border bg-card/50 px-4 py-2 text-sm font-medium text-muted-foreground">
              {a}
            </span>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
        <div className="sketch-card relative overflow-hidden px-6 sm:px-14 py-14 text-center"
          style={{ borderStyle: "dashed" }}>
          <h2 className="font-heading font-extrabold tracking-tight text-3xl sm:text-4xl mb-3">
            Give your agents a sketchbook
          </h2>
          <p className="text-muted-foreground mb-8 max-w-md mx-auto">
            Sign in with Google, spin up a canvas, and connect your first agent in under a minute.
          </p>
          <div className="flex justify-center">
            <GoogleButton testid="cta-login-btn" children="Start drawing — it's free" />
          </div>
          <p className="mt-5 font-hand text-xl text-muted-foreground">no credit card · self-host anytime</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <PenTool className="w-4 h-4" />
            <span className="font-heading font-semibold text-foreground">Sketchpad MCP</span>
            <span>— Open-source Excalidraw MCP canvas</span>
          </div>
          <div className="flex items-center gap-4 font-mono text-xs">
            <span>MIT Licensed</span>
            <a href="https://github.com/wise-toddler/Sketchpad-MCP" target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">GitHub</a>
            <span>Built for builders &amp; agents</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
