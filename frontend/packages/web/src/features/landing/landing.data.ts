import {
  CandlestickChart,
  ShieldCheck,
  Bot,
  Moon,
  Wallet,
  GraduationCap,
  LineChart,
  Lock,
  UserCheck,
  Brain,
  BadgeDollarSign,
  type LucideIcon,
} from "lucide-react";
import { CrescentIcon } from "@/components/icons/icons";

/* ---------- feature cards ---------- */
export const FEATURES: {
  Icon: LucideIcon | typeof CrescentIcon;
  iconColor: string;
  chipBg: string;
  title: string;
  desc: string;
  badge?: string;
}[] = [
  {
    Icon: CandlestickChart,
    iconColor: "text-bull",
    chipBg: "bg-bull/[0.08]",
    title: "PSX Trading Terminal",
    desc: "Candlestick charts, heatmaps, top movers, AI signals — the first Bloomberg-grade PSX terminal on your phone.",
  },
  {
    Icon: ShieldCheck,
    iconColor: "text-warning",
    chipBg: "bg-warning/[0.1]",
    title: "Haqeeqi Daulat™ Engine",
    desc: "See your REAL wealth after PKR devaluation. Pakistan's first devaluation-adjusted portfolio intelligence.",
    badge: "World First",
  },
  {
    Icon: Bot,
    iconColor: "text-ai",
    chipBg: "bg-blue-500/[0.12]",
    title: "AI Financial Advisor",
    desc: "Personalized insights, AI-generated portfolio reports, and a 24/7 finance tutor — powered by Claude AI.",
  },
  {
    Icon: Moon,
    iconColor: "text-bull",
    chipBg: "bg-bull/[0.08]",
    title: "Built for Muslim Investors",
    desc: "Halal stock screening, Zakat calculator, Islamic savings goals — finance aligned with your values.",
  },
  {
    Icon: Wallet,
    iconColor: "text-ai",
    chipBg: "bg-blue-500/[0.12]",
    title: "Complete Finance Manager",
    desc: "Track income, expenses, budgets, bills, and goals — all in one place, in Pakistani Rupees.",
  },
  {
    Icon: GraduationCap,
    iconColor: "text-warning",
    chipBg: "bg-orange-500/[0.12]",
    title: "Financial Education",
    desc: "Beginner to advanced courses in Urdu and English. Earn XP. Build real investing knowledge.",
  },
];

/* ---------- trust / recognition strip (honest, no fabricated logos) ---------- */
export const TRUST_MARKERS: { Icon: LucideIcon; label: string; sub: string }[] = [
  { Icon: LineChart, label: "Live PSX & KSE-100", sub: "Real market data" },
  {
    Icon: CrescentIcon as unknown as LucideIcon,
    label: "Shariah Screening",
    sub: "Halal by design",
  },
  { Icon: Lock, label: "Encrypted", sub: "In transit & at rest" },
  { Icon: UserCheck, label: "No Account Needed", sub: "Explore free first" },
];

export const NAV_LINKS = [
  { label: "Features", href: "#features", to: undefined },
  { label: "About", href: "#about", to: undefined },
  { label: "Pricing", href: undefined, to: "/plans" },
  { label: "Contact", href: "#contact", to: undefined },
] as const;

export const SCATTERED_TICKERS = [
  { text: "HBL", x: "4%", y: "12%", size: 11, opacity: 0.15, depth: 0.3 },
  { text: "+2.41%", x: "14%", y: "28%", size: 10, opacity: 0.12, depth: 0.6 },
  { text: "ENGRO", x: "22%", y: "8%", size: 12, opacity: 0.13, depth: 0.2 },
  { text: "312.45", x: "32%", y: "22%", size: 10, opacity: 0.1, depth: 0.7 },
  { text: "LUCK", x: "44%", y: "15%", size: 11, opacity: 0.11, depth: 0.4 },
  { text: "-0.45%", x: "55%", y: "32%", size: 10, opacity: 0.12, depth: 0.5 },
  { text: "KSE-100", x: "64%", y: "9%", size: 13, opacity: 0.14, depth: 0.25 },
  { text: "78,542", x: "74%", y: "25%", size: 10, opacity: 0.11, depth: 0.65 },
  { text: "OGDC", x: "84%", y: "14%", size: 11, opacity: 0.13, depth: 0.35 },
  { text: "+1.24%", x: "91%", y: "35%", size: 10, opacity: 0.12, depth: 0.55 },
  { text: "FFC", x: "8%", y: "48%", size: 11, opacity: 0.1, depth: 0.45 },
  { text: "168.70", x: "18%", y: "62%", size: 10, opacity: 0.11, depth: 0.7 },
  { text: "+1.08%", x: "28%", y: "45%", size: 10, opacity: 0.09, depth: 0.5 },
  { text: "UBL", x: "38%", y: "58%", size: 12, opacity: 0.12, depth: 0.3 },
  { text: "198.20", x: "50%", y: "70%", size: 10, opacity: 0.1, depth: 0.6 },
  { text: "MCB", x: "60%", y: "52%", size: 11, opacity: 0.11, depth: 0.4 },
  { text: "-0.38%", x: "70%", y: "68%", size: 10, opacity: 0.09, depth: 0.65 },
  { text: "PSO", x: "80%", y: "55%", size: 11, opacity: 0.12, depth: 0.35 },
  { text: "251.30", x: "88%", y: "72%", size: 10, opacity: 0.1, depth: 0.6 },
  { text: "KSE-30", x: "6%", y: "78%", size: 12, opacity: 0.11, depth: 0.3 },
  { text: "24,180", x: "16%", y: "85%", size: 10, opacity: 0.09, depth: 0.7 },
  { text: "DGKC", x: "35%", y: "82%", size: 11, opacity: 0.1, depth: 0.4 },
  { text: "+0.95%", x: "48%", y: "88%", size: 10, opacity: 0.09, depth: 0.55 },
  { text: "POL", x: "62%", y: "80%", size: 11, opacity: 0.11, depth: 0.35 },
  { text: "412.80", x: "72%", y: "90%", size: 10, opacity: 0.08, depth: 0.7 },
  { text: "LOTCHEM", x: "82%", y: "83%", size: 11, opacity: 0.1, depth: 0.45 },
  { text: "+0.62%", x: "92%", y: "78%", size: 10, opacity: 0.09, depth: 0.55 },
  { text: "145.30", x: "42%", y: "38%", size: 10, opacity: 0.1, depth: 0.5 },
] as const;

/* ---------- How NafaIQ Works — 3 steps ---------- */
export const STEPS: {
  step: string;
  title: string;
  label: string;
  desc: string;
  Icon: LucideIcon;
  chips: string[];
}[] = [
  {
    step: "01",
    title: "Track",
    label: "Live Market Data",
    desc: "Connect your portfolio or explore live PSX data instantly — no account required. Real-time KSE-100, watchlists, and pro charts in one terminal.",
    Icon: CandlestickChart,
    chips: ["PSX Live", "Watchlists", "Pro Charts"],
  },
  {
    step: "02",
    title: "Understand",
    label: "Real Wealth Engine",
    desc: "See your real, devaluation-adjusted wealth in plain language. Haqeeqi Daulat™ strips away rupee decay so you know what your money is truly worth.",
    Icon: Brain,
    chips: ["Devaluation-Adjusted", "AI Insights", "Haqeeqi Daulat™"],
  },
  {
    step: "03",
    title: "Decide",
    label: "Decision Engine",
    desc: "Act on personalized moves for investing, saving, and Zakat. Halal-screened recommendations turn insight into confident, values-aligned action.",
    Icon: ShieldCheck,
    chips: ["Recommendations", "Zakat-Aware", "Halal Screened"],
  },
];

/* ---------- FAQ accordion ---------- */
export const FAQS: { Icon: LucideIcon; q: string; a: string }[] = [
  {
    Icon: Lock,
    q: "Is my financial data secure?",
    a: "Your data is encrypted in transit and at rest. NafaIQ never sells your information, and your portfolio details stay private to your account.",
  },
  {
    Icon: CrescentIcon as unknown as LucideIcon,
    q: "Is NafaIQ Shariah compliant?",
    a: "Yes. NafaIQ includes built-in halal stock screening, a Zakat calculator, and Islamic savings goals so you can invest in line with your values.",
  },
  {
    Icon: BadgeDollarSign,
    q: "How much does it cost?",
    a: "The core terminal is free forever — no credit card required. Premium plans add advanced AI reports and deeper analytics. See the Plans page for details.",
  },
  {
    Icon: UserCheck,
    q: "Do I need an account to start?",
    a: "No. You can explore markets, charts, and the Haqeeqi Daulat demo without signing up. Create a free account only when you want to save your portfolio.",
  },
];
