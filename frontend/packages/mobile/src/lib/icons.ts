// Icon access for the app. The web app renders Lucide icons (never raw emoji);
// we do the same with `lucide-react-native`. Re-export the whole set plus a
// small emoji→Lucide map mirroring web `EmojiIcon` for ported data that carries
// emoji fields (goals, lessons, etc.). Extend as screens are built.
import {
  Banknote,
  Bell,
  BookOpen,
  Bot,
  Building2,
  Calculator,
  Calendar,
  Car,
  Coins,
  Flame,
  GraduationCap,
  Home,
  Landmark,
  LineChart,
  type LucideIcon,
  Map as MapIcon,
  NotebookPen,
  PiggyBank,
  Search,
  Shield,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
  Wallet,
} from "lucide-react-native";

export * from "lucide-react-native";

export const emojiIcon: Record<string, LucideIcon> = {
  "🏠": Home,
  "📈": TrendingUp,
  "📉": TrendingDown,
  "📊": LineChart,
  "💰": Coins,
  "💵": Banknote,
  "💸": Banknote,
  "🏦": Building2,
  "🎯": Target,
  "🐷": PiggyBank,
  "👛": Wallet,
  "📚": BookOpen,
  "🎓": GraduationCap,
  "🤖": Bot,
  "🔔": Bell,
  "📅": Calendar,
  // Learn + goals + stat glyphs
  "🗺️": MapIcon,
  "🛡️": Shield,
  "🔍": Search,
  "📒": NotebookPen,
  "🏛️": Landmark,
  "🧮": Calculator,
  "📿": GraduationCap,
  "🔥": Flame,
  "✅": Target,
  "⭐": Star,
  "🏆": Trophy,
  "🕋": Landmark,
  "🕌": Landmark,
  "🚗": Car,
  "🚨": Bell,
};

/** Resolve an emoji to a Lucide icon, falling back to a bell. */
export function iconFor(emoji: string): LucideIcon {
  return emojiIcon[emoji] ?? Bell;
}
