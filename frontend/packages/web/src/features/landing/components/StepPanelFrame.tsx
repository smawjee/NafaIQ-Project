/* ---------- Sticky panel visuals (shared terminal frame) ---------- */
export function StepPanelFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative flex min-h-[300px] w-full max-w-[380px] flex-col rounded-[18px] border border-white/10 dark-surface"
      style={{
        background: "linear-gradient(180deg, rgba(20,28,44,0.96) 0%, rgba(13,19,32,0.96) 100%)",
        boxShadow:
          "0 40px 90px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.02) inset, 0 0 60px rgba(0,212,170,0.07)",
      }}
    >
      {/* window chrome */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-bear/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-bull/70" />
        <span className="ml-auto font-mono text-[9px] font-semibold uppercase tracking-[0.2em] text-text-muted">
          nafaiq · live
        </span>
      </div>
      <div className="flex flex-1 flex-col justify-start p-6">{children}</div>
    </div>
  );
}
