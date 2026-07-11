// Single brand accent for the lesson surface — teal primary, no per-lesson hue drift.
export const ACCENT = "#00d4aa";

export const CALLOUT_META: Record<string, { label: string; color: string; emoji: string }> = {
  tip: { label: "Pro Tip", color: "#00d4aa", emoji: "💡" },
  warning: { label: "Important", color: "#f59e0b", emoji: "⚠️" },
  example: { label: "Real Example", color: "#22c55e", emoji: "📊" },
  note: { label: "Note", color: ACCENT, emoji: "💡" },
};
