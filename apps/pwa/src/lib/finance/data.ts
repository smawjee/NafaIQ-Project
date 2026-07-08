// Finance, goals, learn hub, alerts dummy data

export interface Goal {
  emoji: string;
  name: string;
  target: number;
  saved: number;
  color: "bull" | "warning";
  ai: string;
  date?: string;
}

export const GOALS: Goal[] = [
  {
    emoji: "🕋",
    name: "Hajj Fund",
    target: 1200000,
    saved: 425000,
    color: "bull",
    date: "April 2028",
    ai: "At PKR 25,000/month you'll reach this goal in 31 months. June dining overspend delayed this by ~6 days.",
  },
  {
    emoji: "🚨",
    name: "Emergency Fund",
    target: 300000,
    saved: 180000,
    color: "bull",
    ai: "Almost there! PKR 120,000 remaining. At current rate: 5 months.",
  },
  {
    emoji: "🚗",
    name: "Honda City",
    target: 800000,
    saved: 95000,
    color: "warning",
    ai: "This goal needs attention. Consider increasing monthly contribution by PKR 5,000.",
  },
  {
    emoji: "🕌",
    name: "Umrah 2026",
    target: 250000,
    saved: 60000,
    color: "bull",
    ai: "You need to save PKR 15,833/month to reach this goal by your target.",
  },
];

export interface Txn {
  date: string;
  merchant: string;
  category: string;
  account: string;
  amount: number;
}

export const TRANSACTIONS: Txn[] = [
  {
    date: "June 10",
    merchant: "K-Electric Bill",
    category: "Utilities",
    account: "HBL Current",
    amount: -18420,
  },
  {
    date: "June 9",
    merchant: "Salary — TRG Pakistan",
    category: "Income",
    account: "HBL Current",
    amount: 285000,
  },
  {
    date: "June 8",
    merchant: "Cheezious",
    category: "Food & Dining",
    account: "Meezan Debit",
    amount: -2150,
  },
  { date: "June 7", merchant: "Careem", category: "Transport", account: "Easypaisa", amount: -680 },
  {
    date: "June 7",
    merchant: "Imtiaz Super Market",
    category: "Groceries",
    account: "HBL Current",
    amount: -12480,
  },
  {
    date: "June 5",
    merchant: "Netflix",
    category: "Subscriptions",
    account: "Meezan Debit",
    amount: -1450,
  },
  {
    date: "June 4",
    merchant: "Khaadi",
    category: "Shopping",
    account: "HBL Current",
    amount: -8990,
  },
  {
    date: "June 2",
    merchant: "PSO Fuel",
    category: "Transport",
    account: "HBL Current",
    amount: -7200,
  },
  {
    date: "June 1",
    merchant: "Hajj Fund Transfer",
    category: "Savings",
    account: "Meezan Savings",
    amount: -25000,
  },
];

export interface Budget {
  category: string;
  spent: number;
  limit: number;
  tip?: string;
}

export const BUDGETS: Budget[] = [
  {
    category: "Food & Dining",
    spent: 38000,
    limit: 35000,
    tip: "You've exceeded your dining budget by PKR 3,000. This is delaying your Hajj Fund goal by approximately 6 days.",
  },
  { category: "Utilities", spent: 28000, limit: 30000 },
  { category: "Transport", spent: 18000, limit: 25000 },
  {
    category: "Shopping",
    spent: 15050,
    limit: 12000,
    tip: "Shopping is PKR 3,050 over budget. Trimming this next month frees up cash for your Emergency Fund.",
  },
  { category: "Groceries", spent: 24800, limit: 30000 },
  { category: "Subscriptions", spent: 4350, limit: 5000 },
];

export interface Bill {
  name: string;
  due: string;
  amount: number;
  status: "DUE SOON" | "UPCOMING";
}

export const BILLS: Bill[] = [
  { name: "SNGPL Gas", due: "Jun 15", amount: 4200, status: "DUE SOON" },
  { name: "PTCL Internet", due: "Jun 18", amount: 3500, status: "UPCOMING" },
  { name: "Apartment Rent", due: "Jun 25", amount: 65000, status: "UPCOMING" },
  { name: "Credit Card", due: "Jun 28", amount: 22400, status: "UPCOMING" },
];

export const SPENDING = [
  { name: "Food & Dining", value: 34, amount: 45000, color: "#00d4aa" },
  { name: "Utilities", value: 25, amount: 33000, color: "#3b82f6" },
  { name: "Transport", value: 16, amount: 21000, color: "#f59e0b" },
  { name: "Shopping", value: 13, amount: 17000, color: "#8b5cf6" },
  { name: "Other", value: 12, amount: 16000, color: "#6b7280" },
];

export const INCOME_EXPENSE = [
  { month: "Jan", income: 270000, expense: 128000 },
  { month: "Feb", income: 270000, expense: 119000 },
  { month: "Mar", income: 285000, expense: 134000 },
  { month: "Apr", income: 285000, expense: 127000 },
  { month: "May", income: 285000, expense: 127300 },
  { month: "Jun", income: 285000, expense: 112050 },
];

export interface Lesson {
  emoji: string;
  title: string;
  duration: string;
  level: "Beginner" | "Intermediate";
  status: "Complete" | "In Progress" | "Locked";
  progress?: number;
}

export const LESSONS: Lesson[] = [
  {
    emoji: "📊",
    title: "What is a Candlestick?",
    duration: "4 min",
    level: "Beginner",
    status: "Complete",
  },
  {
    emoji: "📈",
    title: "Understanding RSI",
    duration: "6 min",
    level: "Intermediate",
    status: "Complete",
  },
  {
    emoji: "🗺️",
    title: "Sector Heatmap Guide",
    duration: "3 min",
    level: "Beginner",
    status: "Complete",
  },
  {
    emoji: "🛡️",
    title: "What is a Stop-Loss?",
    duration: "5 min",
    level: "Beginner",
    status: "Complete",
  },
  {
    emoji: "💰",
    title: "Dividend Yield",
    duration: "7 min",
    level: "Intermediate",
    status: "In Progress",
    progress: 60,
  },
  {
    emoji: "🔍",
    title: "5 Candle Patterns",
    duration: "8 min",
    level: "Intermediate",
    status: "Locked",
  },
  {
    emoji: "📒",
    title: "50/30/20 Budget Rule",
    duration: "4 min",
    level: "Beginner",
    status: "Locked",
  },
  { emoji: "🏛️", title: "How PSX Works", duration: "9 min", level: "Beginner", status: "Locked" },
  {
    emoji: "📿",
    title: "Halal Investing & Islamic Finance",
    duration: "8 min",
    level: "Beginner",
    status: "Locked",
  },
  {
    emoji: "🧮",
    title: "Understanding P/E Ratio",
    duration: "5 min",
    level: "Intermediate",
    status: "Locked",
  },
];

export interface GlossaryTerm {
  en: string;
  ur: string;
  def: string;
}

export const GLOSSARY: GlossaryTerm[] = [
  {
    en: "Bull Market",
    ur: "تیزی کا بازار",
    def: "A market trending upward over a sustained period, driven by investor optimism.",
  },
  {
    en: "Bear Market",
    ur: "مندی کا بازار",
    def: "A market in decline, typically a fall of 20% or more from recent highs.",
  },
  {
    en: "Dividend",
    ur: "منافع",
    def: "A share of company profit paid out to shareholders, usually in cash.",
  },
  {
    en: "Market Cap",
    ur: "مارکیٹ کیپ",
    def: "Share price × total shares outstanding — the company's total market value.",
  },
  {
    en: "P/E Ratio",
    ur: "قیمت آمدنی",
    def: "Price paid per rupee of earnings. A lower P/E may signal better value.",
  },
  {
    en: "RSI",
    ur: "آر ایس آئی",
    def: "Momentum indicator from 0–100. Above 70 is overbought, below 30 oversold.",
  },
  {
    en: "Volume",
    ur: "حجم",
    def: "Number of shares traded in a given period. High volume confirms moves.",
  },
  {
    en: "Blue Chip",
    ur: "بلیو چپ",
    def: "A large, stable, well-known company stock with a reliable track record.",
  },
  {
    en: "Stop Loss",
    ur: "اسٹاپ لاس",
    def: "An automatic sell order placed to limit losses on a position.",
  },
  {
    en: "Circuit Breaker",
    ur: "سرکٹ بریکر",
    def: "A PSX auto-halt triggered when the index moves ±5% to curb volatility.",
  },
];

export interface Alert {
  emoji: string;
  title: string;
  type: string;
  meta: string;
  on: boolean;
}

export const ALERTS: Alert[] = [
  {
    emoji: "🔔",
    title: "HBL above PKR 150",
    type: "Stock Price Alert",
    meta: "Created Jun 10",
    on: true,
  },
  {
    emoji: "📅",
    title: "SNGPL Gas due in 3 days",
    type: "Bill Reminder",
    meta: "Recurring monthly",
    on: true,
  },
  {
    emoji: "💸",
    title: "Food & Dining 80% of budget",
    type: "Budget Alert",
    meta: "June 2025",
    on: true,
  },
  {
    emoji: "🎯",
    title: "Hajj Fund 50% reached",
    type: "Goal Milestone",
    meta: "One-time",
    on: true,
  },
  {
    emoji: "📉",
    title: "LUCK below PKR 800",
    type: "Stock Price Alert",
    meta: "Created Jun 12",
    on: false,
  },
];

export interface Notif {
  time: string;
  emoji: string;
  msg: string;
  read: boolean;
}

export const NOTIFS: Notif[] = [
  {
    time: "Jun 10, 09:15",
    emoji: "📈",
    msg: "HBL crossed above MA50 — Strong Buy signal triggered",
    read: true,
  },
  {
    time: "Jun 10, 08:00",
    emoji: "📅",
    msg: "K-Electric bill due in 3 days — PKR 18,420",
    read: true,
  },
  {
    time: "Jun 9, 18:30",
    emoji: "💸",
    msg: "Food & Dining budget 92% used — PKR 32,340 of 35,000",
    read: false,
  },
  {
    time: "Jun 9, 08:00",
    emoji: "🎯",
    msg: "Great news! Emergency Fund reached 60% of target",
    read: false,
  },
];
