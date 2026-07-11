export function ZakatNumberInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: number;
  onChange: (n: number) => void;
  ariaLabel: string;
}) {
  return (
    <input
      inputMode="numeric"
      aria-label={ariaLabel}
      value={value === 0 ? "" : String(value)}
      placeholder="0"
      onChange={(e) => {
        const cleaned = e.target.value.replace(/[^0-9]/g, "");
        onChange(cleaned === "" ? 0 : Number(cleaned));
      }}
      className="w-[150px] rounded-[8px] border border-white/[0.08] bg-elevated/60 px-3 py-2 text-right font-mono text-sm font-semibold tabular-nums text-text-primary outline-none transition-colors focus:border-primary/50 focus:bg-elevated"
    />
  );
}
