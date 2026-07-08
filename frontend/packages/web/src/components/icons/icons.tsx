import type { LucideIcon } from "lucide-react";
import {
  ShieldAlert,
  ShieldCheck,
  Car,
  BarChart2,
  TrendingUp,
  TrendingDown,
  Grid3X3,
  Percent,
  Eye,
  CandlestickChart,
  Calculator,
  Building2,
  Bell,
  Calendar,
  Wallet,
  Target,
  Cpu,
  Briefcase,
  GraduationCap,
  Lightbulb,
  AlertTriangle,
  Pin,
  Inbox,
  MessageCircle,
  Video,
  BookOpen,
  CheckCircle2,
  Star,
  Trophy,
  Brain,
  PartyPopper,
  Flame,
  FileText,
  Layers,
  Circle,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

/** Minimal, geometrically precise crescent for Islamic / Halal contexts. */
export function CrescentIcon({
  size = 16,
  className,
  strokeWidth = 1.5,
}: {
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M18.5 17.5A7.5 7.5 0 1 1 13 4.2a6 6 0 1 0 5.5 13.3Z" />
    </svg>
  );
}

/** Solid "PK" text badge replacing the 🇵🇰 flag emoji. */
export function PkBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[5px] border border-bull/40 bg-bull/10 px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-wide text-bull",
        className,
      )}
    >
      PK
    </span>
  );
}

/** Maps every emoji used across the data layer to a precise Lucide icon. */
const EMOJI_MAP: Record<string, LucideIcon> = {
  "🚨": ShieldAlert,
  "🚗": Car,
  "📊": BarChart2,
  "📈": TrendingUp,
  "📉": TrendingDown,
  "🗺️": Grid3X3,
  "🛡️": ShieldCheck,
  "💰": Percent,
  "🔍": Eye,
  "🕯️": CandlestickChart,
  "📒": Calculator,
  "🏛️": Building2,
  "🧮": Calculator,
  "🔔": Bell,
  "📅": Calendar,
  "💸": Wallet,
  "🎯": Target,
  "🤖": Cpu,
  "💼": Briefcase,
  "📚": GraduationCap,
  "💡": Lightbulb,
  "⚠️": AlertTriangle,
  "📌": Pin,
  "📭": Inbox,
  "💬": MessageCircle,
  "🎬": Video,
  "📖": BookOpen,
  "📄": FileText,
  "✅": CheckCircle2,
  "✓": CheckCircle2,
  "⭐": Star,
  "🏆": Trophy,
  "🧠": Brain,
  "🎉": PartyPopper,
  "🔥": Flame,
  "🃏": Layers,
  "🟢": Circle,
  "⚪": Circle,
};

const CRESCENT_EMOJI = new Set(["🕋", "🕌", "📿"]);

/**
 * Renders the correct Lucide (or crescent) icon for a given emoji string.
 * Falls back to Sparkles for anything unmapped so the UI never shows a raw glyph.
 */
export function EmojiIcon({
  emoji,
  className,
  size,
  strokeWidth = 1.5,
}: {
  emoji: string;
  className?: string;
  size?: number;
  strokeWidth?: number;
}) {
  if (CRESCENT_EMOJI.has(emoji)) {
    return <CrescentIcon size={size ?? 16} className={className} strokeWidth={strokeWidth} />;
  }
  const Icon = EMOJI_MAP[emoji] ?? Sparkles;
  return <Icon className={className} size={size} strokeWidth={strokeWidth} />;
}
