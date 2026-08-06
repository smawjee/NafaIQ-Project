export function TrackPanel() {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bull" />
        <span className="text-[10px] font-bold tracking-widest text-bull">LIVE</span>
        <span className="ms-auto text-[10px] font-semibold uppercase tracking-widest text-text-muted">
          PSX Market
        </span>
      </div>
      <div className="mt-6">
        <div className="text-[11px] text-text-muted">KSE-100 Index</div>
        <div className="mt-1 font-mono text-[40px] font-bold leading-none text-text-primary">
          78,542.10
        </div>
        <div className="mt-2 font-mono text-sm font-semibold text-bull">+968.30 · +1.24% ▲</div>
      </div>
      <div className="mt-6 flex h-16 items-end gap-1.5">
        {[40, 55, 35, 70, 50, 80, 65, 90, 75, 95, 82, 96].map((h, i) => (
          <div key={i} className="flex-1 rounded-t-sm bg-bull/70" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}
