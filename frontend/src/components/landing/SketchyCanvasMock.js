import { motion } from "framer-motion";

// A faux Excalidraw whiteboard where an AI agent + a human co-draw an architecture
// diagram in real time. Pure SVG + framer-motion — no real canvas, just vibes.
export default function SketchyCanvasMock() {
  const stroke = "var(--ink)";
  return (
    <div
      data-testid="hero-canvas-preview"
      className="sketch-card relative w-full overflow-hidden p-3 sm:p-4"
      style={{ ["--ink"]: "currentColor" }}
    >
      {/* fake window chrome */}
      <div className="flex items-center gap-1.5 mb-2 px-1">
        <span className="w-3 h-3 rounded-full bg-[#ff5f57] border border-black/20" />
        <span className="w-3 h-3 rounded-full bg-[#febc2e] border border-black/20" />
        <span className="w-3 h-3 rounded-full bg-[#28c840] border border-black/20" />
        <span className="ml-2 font-hand text-lg leading-none text-muted-foreground">system-architecture.excalidraw</span>
        <span className="ml-auto flex -space-x-1.5">
          <span className="w-5 h-5 rounded-full bg-violet-500 border-2 border-background text-[9px] grid place-items-center text-white font-bold">AI</span>
          <span className="w-5 h-5 rounded-full bg-orange-500 border-2 border-background text-[9px] grid place-items-center text-white font-bold">A</span>
        </span>
      </div>

      <div className="relative rounded-lg overflow-hidden paper-grid aspect-[4/3]">
        <svg viewBox="0 0 400 300" className="w-full h-full text-foreground">
          {/* node 1 */}
          <motion.g initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <rect x="28" y="40" width="120" height="52" rx="8" fill="#a5f3fc" stroke={stroke} strokeWidth="2" />
            <text x="88" y="70" textAnchor="middle" className="font-hand" fontSize="19" fill="#0b3b47">React UI</text>
          </motion.g>

          {/* node 2 */}
          <motion.g initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.55 }}>
            <rect x="250" y="38" width="128" height="52" rx="8" fill="#fde68a" stroke={stroke} strokeWidth="2" />
            <text x="314" y="60" textAnchor="middle" className="font-hand" fontSize="18" fill="#5a3a0a">FastAPI</text>
            <text x="314" y="80" textAnchor="middle" className="font-hand" fontSize="15" fill="#5a3a0a">gateway</text>
          </motion.g>

          {/* node 3 */}
          <motion.g initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.15 }}>
            <rect x="250" y="188" width="128" height="52" rx="8" fill="#ddd6fe" stroke={stroke} strokeWidth="2" />
            <text x="314" y="210" textAnchor="middle" className="font-hand" fontSize="18" fill="#3b1f7a">MCP Engine</text>
            <text x="314" y="230" textAnchor="middle" className="font-hand" fontSize="15" fill="#3b1f7a">+ agents</text>
          </motion.g>

          {/* node 4 */}
          <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}>
            <rect x="40" y="190" width="118" height="48" rx="8" fill="#dcfce7" stroke={stroke} strokeWidth="2" />
            <text x="99" y="220" textAnchor="middle" className="font-hand" fontSize="18" fill="#14532d">MongoDB</text>
          </motion.g>

          {/* connectors */}
          <motion.path d="M148 66 C 200 66, 205 64, 248 64" fill="none" stroke={stroke} strokeWidth="2"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.7, duration: 0.6 }} />
          <motion.path d="M314 90 C 314 130, 314 150, 314 186" fill="none" stroke={stroke} strokeWidth="2"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 1.0, duration: 0.5 }} />
          <motion.path d="M250 214 C 200 214, 170 214, 160 214" fill="none" stroke={stroke} strokeWidth="2" strokeDasharray="5 5"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 1.35, duration: 0.5 }} />
          {/* arrow head */}
          <motion.path d="M248 64 l -9 -4 M248 64 l -9 5" stroke={stroke} strokeWidth="2" fill="none"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.3 }} />
        </svg>

        {/* live cursor tags */}
        <motion.div
          className="absolute"
          initial={{ left: "20%", top: "55%" }}
          animate={{ left: ["20%", "62%", "58%"], top: ["55%", "20%", "62%"] }}
          transition={{ duration: 4, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" className="text-violet-500 drop-shadow">
            <path fill="currentColor" d="M4 2l7 18 2.5-7.5L21 10z" />
          </svg>
          <span className="ml-3 -mt-1 inline-block rounded bg-violet-500 px-1.5 py-0.5 text-[10px] font-semibold text-white whitespace-nowrap">Claude (Agent)</span>
        </motion.div>
        <div className="absolute left-[42%] top-[70%]">
          <svg width="18" height="18" viewBox="0 0 24 24" className="text-orange-500 drop-shadow">
            <path fill="currentColor" d="M4 2l7 18 2.5-7.5L21 10z" />
          </svg>
          <span className="ml-3 -mt-1 inline-block rounded bg-orange-500 px-1.5 py-0.5 text-[10px] font-semibold text-white whitespace-nowrap">Alex (You)</span>
        </div>
      </div>

      {/* agent log line */}
      <div className="mt-2.5 flex items-center gap-2 px-1 font-mono text-[11px] text-muted-foreground">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        <span className="truncate">agent → <span className="text-foreground">batch_create_elements</span> · 4 nodes, 3 arrows · synced ✓</span>
      </div>
    </div>
  );
}
