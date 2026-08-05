// Learn Hub content: lessons, paths, quizzes, flashcards.
import { GLOSSARY } from "../finance/data";

export type LessonStatus = "complete" | "in-progress" | "not-started";

export type ContentBlock =
  | { type: "p"; text: string }
  | { type: "callout"; kind: "tip" | "warning" | "example" | "note"; text: string }
  | { type: "formula"; lines: string[] }
  | { type: "table"; head: string[]; rows: string[][] };

export interface LessonSection {
  id: string;
  heading: string;
  blocks: ContentBlock[];
}

export interface QuizQuestion {
  q: string;
  options: string[];
  correct: number; // index into options (content order)
  explanation: string;
}

export interface LessonContent {
  id: string;
  emoji: string;
  title: string;
  subtitle: string;
  category: string;
  accent: string; // hex accent color
  duration: string;
  level: "Beginner" | "Intermediate" | "Advanced";
  origin?: "official" | "generated";
  language?: "en" | "ur";
  sources?: Array<{ sourceId: string; title: string; heading?: string | null; lessonId?: string | null }>;
  projectId?: string;
  videoStatus?: string;
  rewardMode?: "xp" | "practice";
  generatedAt?: string | null;
  sourceKind?: "topic" | "pdf";
  documentName?: string | null;
  type: "article" | "video";
  videoUrl?: string;
  captionsUrl?: string | null;
  posterUrl?: string | null;
  presets: string[];
  sections: LessonSection[];
  quiz: QuizQuestion[];
}

export interface LearningPath {
  id: string;
  emoji: string;
  accent: string;
  title: string;
  description: string;
  lessonIds: string[];
  estMin: number;
}

export const LEARNING_PATHS: LearningPath[] = [
  {
    id: "psx-starter",
    emoji: "📊",
    accent: "#00d4aa",
    title: "PSX Investor Starter",
    description: "From zero to your first trade",
    lessonIds: ["candlestick", "psx", "stop-loss", "patterns"],
    estMin: 26,
  },
  {
    id: "technical",
    emoji: "📈",
    accent: "#8b5cf6",
    title: "Technical Analysis",
    description: "Charts, patterns, and indicators",
    lessonIds: ["rsi", "patterns", "heatmap"],
    estMin: 19,
  },
  {
    id: "islamic",
    emoji: "📿",
    accent: "#22c55e",
    title: "Islamic Finance",
    description: "Halal investing principles",
    lessonIds: ["halal", "dividend"],
    estMin: 15,
  },
  {
    id: "personal",
    emoji: "💰",
    accent: "#f59e0b",
    title: "Personal Finance",
    description: "Budget, save, and grow",
    lessonIds: ["budget", "dividend", "pe-ratio"],
    estMin: 18,
  },
];

// Title -> id mapping shared with the existing LESSONS list.
export const LESSON_ID_BY_TITLE: Record<string, string> = {
  "What is a Candlestick?": "candlestick",
  "Understanding RSI": "rsi",
  "Sector Heatmap Guide": "heatmap",
  "What is a Stop-Loss?": "stop-loss",
  "Dividend Yield": "dividend",
  "5 Candle Patterns": "patterns",
  "50/30/20 Budget Rule": "budget",
  "How PSX Works": "psx",
  "Halal Investing & Islamic Finance": "halal",
  "Understanding P/E Ratio": "pe-ratio",
};

// Bespoke per-lesson content lives inline in LESSON_CONTENT below.

export const LESSON_CONTENT: Record<string, LessonContent> = {
  candlestick: {
    id: "candlestick",
    emoji: "📊",
    title: "What is a Candlestick?",
    subtitle: "The building block of every PSX price chart",
    category: "PSX Basics",
    accent: "#00d4aa",
    duration: "4 min",
    level: "Beginner",
    type: "article",
    presets: ["What's a Doji candle?", "Show me a bullish pattern", "How do I use this on PSX?"],
    sections: [
      {
        id: "introduction",
        heading: "Introduction",
        blocks: [
          {
            type: "p",
            text: "Before you can read any PSX chart, you need to understand the building block of all price charts: the candlestick. Every candle tells you the story of a stock during a specific time period — whether buyers or sellers were in control.",
          },
          {
            type: "callout",
            kind: "tip",
            text: "Each candle on a 1-day chart represents one full trading day on PSX (9:30 AM to 3:30 PM). On a 1-hour chart, each candle = 1 hour of trading.",
          },
        ],
      },
      {
        id: "anatomy-of-a-candlestick",
        heading: "Anatomy of a Candlestick",
        blocks: [
          { type: "p", text: "Every candlestick has four data points, known as OHLC:" },
          {
            type: "formula",
            lines: [
              "O — Open:   Price at market open",
              "H — High:   Highest price reached",
              "L — Low:    Lowest price reached",
              "C — Close:  Price at market close",
            ],
          },
          {
            type: "p",
            text: "The thick part of the candle is called the BODY. It stretches from the Open to the Close price. The thin lines above and below the body are called WICKS (or shadows) — they show how far price traveled beyond the open/close range.",
          },
        ],
      },
      {
        id: "bullish-vs-bearish-candles",
        heading: "Bullish vs Bearish Candles",
        blocks: [
          {
            type: "p",
            text: "The color of a candle tells you instantly who won the battle between buyers and sellers that period:",
          },
          {
            type: "table",
            head: ["Type", "Color", "Meaning", "Close vs Open"],
            rows: [
              ["Bullish", "Teal/Green", "Buyers in control", "Close > Open"],
              ["Bearish", "Red", "Sellers in control", "Close < Open"],
              ["Doji", "Gray", "Indecision, no clear winner", "Close ≈ Open"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "HBL on June 5, 2026: Open: PKR 139.20 | High: PKR 143.80 | Low: PKR 138.50 | Close: 142.50. Result: GREEN candle. Body = 139.20 to 142.50. Upper wick = 142.50 to 143.80. Lower wick = 139.20 to 138.50. HBL had a bullish day.",
          },
        ],
      },
      {
        id: "what-the-wicks-tell-you",
        heading: "What the Wicks Tell You",
        blocks: [
          {
            type: "p",
            text: "Wicks are often more informative than the body. A LONG UPPER WICK means price tried to go higher but was pushed back down by sellers — a warning sign for bulls. A LONG LOWER WICK means price tried to drop but buyers stepped in and rescued it — a bullish signal. SHORT WICKS on both sides mean price moved decisively in one direction — strong conviction.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "Never look at a single candlestick in isolation. One candle is just one data point. Patterns formed by 2-3 candles together are far more meaningful. Check the '5 Candle Patterns' lesson next.",
          },
        ],
      },
      {
        id: "why-this-matters-on-psx",
        heading: "Why This Matters on PSX",
        blocks: [
          {
            type: "p",
            text: "PSX stocks often show very clear candlestick signals because retail investor sentiment is strong. During the 2023 market recovery, the KSE-100 formed a textbook 'Morning Star' pattern (3 candles) that preceded a 4,000-point rally. Candlestick readers saw it coming.",
          },
          {
            type: "callout",
            kind: "note",
            text: "Candlesticks describe what already happened — they hint at probabilities, not certainties. Always pair them with risk management like a stop-loss.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "What does the BODY of a candlestick represent?",
        options: [
          "The highest and lowest price of the day",
          "The opening and closing price of the period",
          "The total volume traded",
          "The difference between two moving averages",
        ],
        correct: 1,
        explanation:
          "The body (thick part) shows where price OPENED and CLOSED. The wicks/shadows show the HIGH and LOW extremes.",
      },
      {
        q: "A GREEN (teal) candlestick on NafaIQ means...",
        options: [
          "The stock is halal certified",
          "Trading volume was above average",
          "The closing price was LOWER than the opening price",
          "The closing price was HIGHER than the opening price",
        ],
        correct: 3,
        explanation:
          "Green/teal = price closed higher than it opened = bullish (buying pressure). Red = closed lower = bearish.",
      },
      {
        q: "On PSX, if HBL opened at 140 and closed at 145, the candlestick body would be...",
        options: [
          "Red, spanning 140 to 145",
          "Green, spanning 140 to 145",
          "Red, spanning 145 to 140",
          "The color depends on volume, not price direction",
        ],
        correct: 1,
        explanation:
          "Price went UP (140→145), so the candle is GREEN. Body runs from open (140) at bottom to close (145) at top.",
      },
    ],
  },

  rsi: {
    id: "rsi",
    emoji: "📈",
    title: "Understanding RSI",
    subtitle: "Reading momentum with the Relative Strength Index",
    category: "Technical Analysis",
    accent: "#8b5cf6",
    duration: "6 min",
    level: "Intermediate",
    type: "video",
    presets: [
      "What's RSI divergence?",
      "Best RSI settings for PSX?",
      "Explain overbought vs oversold",
    ],
    sections: [
      {
        id: "introduction",
        heading: "Introduction",
        blocks: [
          {
            type: "p",
            text: "The Relative Strength Index (RSI) is a momentum oscillator that moves between 0 and 100. It helps you gauge whether a stock has been bought or sold too aggressively in the recent past.",
          },
          {
            type: "callout",
            kind: "tip",
            text: "The default RSI period is 14. On PSX daily charts, RSI(14) works well for most blue-chip stocks like HBL and ENGRO.",
          },
        ],
      },
      {
        id: "the-rsi-formula",
        heading: "The RSI Formula",
        blocks: [
          { type: "p", text: "RSI compares the size of recent gains to recent losses:" },
          {
            type: "formula",
            lines: ["RSI = 100 - [100 / (1 + RS)]", "Where RS = Avg Gain / Avg Loss"],
          },
        ],
      },
      {
        id: "overbought-and-oversold",
        heading: "Overbought and Oversold",
        blocks: [
          {
            type: "p",
            text: "An RSI above 70 is considered overbought (buying may be stretched), while below 30 is oversold (selling may be exhausted). These are warnings, not automatic buy/sell signals.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "In strong trends RSI can stay overbought or oversold for a long time. Never short a stock just because RSI is above 70.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "RSI stands for...",
        options: [
          "Relative Stability Index",
          "Return on Stock Investment",
          "Relative Strength Index",
          "Risk Sensitivity Indicator",
        ],
        correct: 2,
        explanation:
          "RSI = Relative Strength Index. Developed by J. Welles Wilder in 1978. Measures momentum, not absolute strength.",
      },
      {
        q: "An RSI reading of 78 on HBL most likely suggests...",
        options: [
          "HBL is in a strong downtrend",
          "HBL is oversold and may bounce",
          "HBL is overbought and may face selling pressure",
          "HBL has very low trading volume",
        ],
        correct: 2,
        explanation:
          "RSI above 70 = overbought zone. Does not mean sell immediately, but warns that buying momentum is stretched.",
      },
      {
        q: "RSI of 25 on ENGRO in a downtrend typically signals...",
        options: [
          "Sell immediately — trend will continue forever",
          "Oversold conditions — potential reversal or bounce",
          "Overbought — price is too high",
          "No signal — RSI below 30 is irrelevant",
        ],
        correct: 1,
        explanation:
          "Below 30 = oversold. In a strong downtrend, RSI can stay low — but it warns of potential exhaustion of sellers.",
      },
    ],
  },

  "stop-loss": {
    id: "stop-loss",
    emoji: "🛡️",
    title: "What is a Stop-Loss?",
    subtitle: "Protecting your capital with a planned exit",
    category: "Risk Management",
    accent: "#f59e0b",
    duration: "5 min",
    level: "Beginner",
    type: "article",
    presets: [
      "What's a trailing stop-loss?",
      "How to avoid stop hunts?",
      "PSX circuit breaker vs stop-loss?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "Introduction",
        blocks: [
          {
            type: "p",
            text: "A stop-loss is a pre-set order that automatically sells your position once price falls to a level you choose in advance. It is the single most important tool for protecting your capital.",
          },
          {
            type: "callout",
            kind: "tip",
            text: "Decide your stop-loss BEFORE you buy, while you are calm and objective — not after price is already falling.",
          },
        ],
      },
      {
        id: "how-it-works",
        heading: "How It Works",
        blocks: [
          {
            type: "p",
            text: "If you buy LUCK at PKR 845 and set a stop-loss at PKR 820, your broker will trigger a sell order if price touches 820 — capping your loss at roughly PKR 25 per share.",
          },
          {
            type: "formula",
            lines: ["Max Loss = (Entry - Stop) × Shares", "Example: (845 - 820) × 100 = PKR 2,500"],
          },
        ],
      },
      {
        id: "where-to-place-it",
        heading: "Where to Place It",
        blocks: [
          {
            type: "p",
            text: "Place your stop-loss just below a meaningful support level or recent swing low — the level where your reason for buying would no longer be valid. Arbitrary percentages are weaker than technical levels.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "In fast markets your stop may execute slightly below your level (slippage). Build a small buffer into your risk plan.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "What is the PRIMARY purpose of a stop-loss order?",
        options: [
          "To maximize profit on winning trades",
          "To automatically buy more shares when price drops",
          "To limit your maximum loss on a position",
          "To predict when a stock will reverse direction",
        ],
        correct: 2,
        explanation:
          "Stop-loss = pre-set exit. You decide in advance how much loss you can accept. Removes emotion from the decision.",
      },
      {
        q: "You buy LUCK at PKR 845. You set a stop-loss at PKR 820. If LUCK drops to 820, what happens?",
        options: [
          "Nothing — you must manually sell",
          "Your broker alerts you but waits for confirmation",
          "Your position is automatically sold at ~PKR 820",
          "You automatically buy more LUCK at the lower price",
        ],
        correct: 2,
        explanation:
          "A stop-loss triggers a SELL order when price hits your set level. Execution may be slightly below 820 in fast markets (slippage).",
      },
      {
        q: "Where should a stop-loss ideally be placed?",
        options: [
          "Exactly 5% below entry price, always",
          "Just below a key support level or recent swing low",
          "At your average cost price to break even",
          "Stop-losses are only for beginners — experts don't use them",
        ],
        correct: 1,
        explanation:
          "Technical placement beats arbitrary percentages. Below support = the level where your trade thesis is invalidated.",
      },
    ],
  },

  dividend: {
    id: "dividend",
    emoji: "💰",
    title: "Dividend Yield",
    subtitle: "Measuring the income a stock pays you",
    category: "Fundamentals",
    accent: "#22c55e",
    duration: "7 min",
    level: "Intermediate",
    type: "article",
    presets: [
      "What is a payout ratio?",
      "Best dividend stocks on PSX?",
      "Are dividends taxed in Pakistan?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "Introduction",
        blocks: [
          {
            type: "p",
            text: "Dividend yield tells you how much cash income a stock pays relative to its price. It is the favourite metric of income-focused PSX investors who want regular returns, not just capital gains.",
          },
          {
            type: "callout",
            kind: "tip",
            text: "High-dividend PSX names like FFC and HUBCO are popular with retirees and conservative investors seeking steady payouts.",
          },
        ],
      },
      {
        id: "the-formula",
        heading: "The Formula",
        blocks: [
          {
            type: "p",
            text: "Dividend yield is the annual dividend per share divided by the current price, expressed as a percentage:",
          },
          {
            type: "formula",
            lines: [
              "Dividend Yield = (Annual Dividend / Share Price) × 100",
              "Example: (16 / 168) × 100 = 9.52%",
            ],
          },
        ],
      },
      {
        id: "price-and-yield",
        heading: "Price and Yield Move Opposite",
        blocks: [
          {
            type: "p",
            text: "Because price is the denominator, a rising share price (with the same dividend) lowers the yield, and a falling price raises it. A very high yield can sometimes be a warning that the market expects a dividend cut.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "An unusually high yield is not always good news — check whether the company can actually sustain the payout.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "Dividend Yield formula is...",
        options: [
          "Share Price ÷ Annual Dividend",
          "Annual Dividend × Share Price",
          "Annual Dividend ÷ Share Price × 100",
          "Net Profit ÷ Total Shares",
        ],
        correct: 2,
        explanation:
          "Yield = (Annual DPS / Current Price) × 100. If FFC pays PKR 16/share and trades at 168, yield = 9.5%.",
      },
      {
        q: "FFC pays PKR 16 dividend. Current price is PKR 168. What is the dividend yield?",
        options: ["16%", "9.52%", "168%", "10.5%"],
        correct: 1,
        explanation:
          "(16 ÷ 168) × 100 = 9.52%. FFC is known as a high-dividend stock on PSX — attractive for income investors.",
      },
      {
        q: "If a stock's PRICE rises but dividend stays the same...",
        options: [
          "Dividend yield increases",
          "Dividend yield stays the same",
          "Dividend yield decreases",
          "The company must increase its dividend",
        ],
        correct: 2,
        explanation:
          "Yield = dividend ÷ price. Higher price = lower yield (same numerator, bigger denominator). Inverse relationship.",
      },
    ],
  },

  heatmap: {
    id: "heatmap",
    emoji: "🗺️",
    title: "Sector Heatmap Guide",
    subtitle: "Spotting market rotation at a glance",
    category: "Technical Analysis",
    accent: "#3b82f6",
    duration: "3 min",
    level: "Beginner",
    type: "article",
    presets: [
      "What is sector rotation?",
      "Why are banks green today?",
      "How often does the heatmap update?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "Reading the Colours",
        blocks: [
          {
            type: "p",
            text: "A sector heatmap shows the whole market on one screen. Each tile is a sector or stock; its colour shows performance — green for gains, red for losses — and its size usually reflects market weight. One glance tells you where money is flowing today.",
          },
          {
            type: "callout",
            kind: "note",
            text: "Deeper green or red means a bigger move. A pale tile is roughly flat, not necessarily 'safe' — it just hasn't moved much.",
          },
        ],
      },
      {
        id: "the-core-idea",
        heading: "Spotting Sector Rotation",
        blocks: [
          {
            type: "p",
            text: "Markets move in rotations — money leaves one sector and crowds into another. When banks are deep green while cement and autos bleed red, capital is rotating toward financials. The heatmap makes that shift obvious before headlines explain it.",
          },
          {
            type: "callout",
            kind: "example",
            text: "If oil & gas tiles turn green across the board after a crude price jump, that's sector-wide momentum — not a one-stock story.",
          },
        ],
      },
      {
        id: "why-it-matters",
        heading: "Using It Without Being Fooled",
        blocks: [
          {
            type: "p",
            text: "The heatmap is a starting point, not a buy list. A green sector tells you where attention is, but you still confirm the individual stock's chart and fundamentals before acting.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "A single green day doesn't make a trend. Don't chase a hot sector at the top — confirm with a few sessions of follow-through.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "On a sector heatmap, what does a deep red tile indicate?",
        options: ["A large gain", "A large loss", "No change", "A halted stock"],
        correct: 1,
        explanation: "Red means a decline, and a deeper shade indicates a bigger loss.",
      },
      {
        q: "Banks are green while autos and cement are red. What is this likely showing?",
        options: [
          "A data error",
          "Sector rotation toward financials",
          "The market is closed",
          "Nothing meaningful",
        ],
        correct: 1,
        explanation:
          "Money moving into one sector while leaving others is classic sector rotation.",
      },
      {
        q: "How should you treat a hot green sector on the heatmap?",
        options: [
          "Buy any stock in it immediately",
          "As a starting point — confirm the individual stock before acting",
          "Ignore it completely",
          "Assume it will fall tomorrow",
        ],
        correct: 1,
        explanation:
          "The heatmap shows where attention is; you still confirm the specific stock's chart and fundamentals.",
      },
    ],
  },

  patterns: {
    id: "patterns",
    emoji: "🕯️",
    title: "5 Candle Patterns",
    subtitle: "High-probability setups every trader should know",
    category: "Technical Analysis",
    accent: "#8b5cf6",
    duration: "8 min",
    level: "Intermediate",
    type: "video",
    presets: [
      "What is a Morning Star?",
      "How reliable are patterns?",
      "Bullish vs bearish engulfing?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "Why Patterns Work",
        blocks: [
          {
            type: "p",
            text: "Candle patterns are short, repeatable shapes that hint at a shift in who's winning — buyers or sellers. They don't predict the future; they summarise a tug-of-war in price so you can act with more context than a single candle gives.",
          },
          {
            type: "callout",
            kind: "note",
            text: "A pattern at a key level (support, resistance, a moving average) is far more meaningful than the same pattern in the middle of nowhere.",
          },
        ],
      },
      {
        id: "the-core-idea",
        heading: "The Five to Know",
        blocks: [
          {
            type: "p",
            text: "Master these five and you'll recognise the majority of high-probability setups on PSX charts.",
          },
          {
            type: "table",
            head: ["Pattern", "Signals", "What it means"],
            rows: [
              ["Bullish Engulfing", "Reversal up", "A big green candle swallows the prior red one"],
              [
                "Bearish Engulfing",
                "Reversal down",
                "A big red candle swallows the prior green one",
              ],
              ["Hammer", "Reversal up", "Long lower wick — sellers pushed down, buyers won back"],
              [
                "Shooting Star",
                "Reversal down",
                "Long upper wick — buyers pushed up, sellers reclaimed",
              ],
              ["Morning Star", "Reversal up", "Three candles: drop, pause, strong recovery"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "A hammer forming right at a stock's prior support level, on rising volume, is a classic 'buyers are stepping in' signal.",
          },
        ],
      },
      {
        id: "why-it-matters",
        heading: "Confirm Before You Act",
        blocks: [
          {
            type: "p",
            text: "A pattern is a hint, not a trigger. The strongest signals are confirmed by volume and by the next candle continuing in the expected direction. On a thin PSX small-cap, a single candle can be noise.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "Never trade a pattern in isolation. Wait for confirmation and always pair it with a stop-loss to cap the cost of being wrong.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "What does a bullish engulfing pattern look like?",
        options: [
          "A small green candle inside a large red one",
          "A large green candle that fully covers the prior red candle's body",
          "Two red candles in a row",
          "A single candle with no wicks",
        ],
        correct: 1,
        explanation:
          "Bullish engulfing is a large green candle whose body swallows the previous red candle — a reversal-up signal.",
      },
      {
        q: "A candle with a long lower wick and small body near support is a…",
        options: ["Shooting Star", "Hammer", "Bearish Engulfing", "Doji of no meaning"],
        correct: 1,
        explanation:
          "A long lower wick means sellers pushed price down but buyers reclaimed it — a hammer, especially strong at support.",
      },
      {
        q: "What makes a candle pattern more trustworthy?",
        options: [
          "Appearing in the middle of a range with low volume",
          "Confirmation from volume and the following candle, at a key level",
          "Being on a very thin small-cap",
          "Ignoring all other signals",
        ],
        correct: 1,
        explanation:
          "Patterns are strongest when they form at key levels and are confirmed by volume and follow-through.",
      },
    ],
  },

  budget: {
    id: "budget",
    emoji: "📒",
    title: "50/30/20 Budget Rule",
    subtitle: "A simple framework for managing your salary",
    category: "Personal Finance",
    accent: "#f59e0b",
    duration: "4 min",
    level: "Beginner",
    type: "article",
    presets: [
      "How do I start budgeting?",
      "What counts as a 'want'?",
      "Adapting 50/30/20 for Pakistan?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "The Rule in One Line",
        blocks: [
          {
            type: "p",
            text: "The 50/30/20 rule splits your take-home salary into three buckets: 50% for needs, 30% for wants, and 20% for savings and debt repayment. It's popular because it's simple enough to actually stick to.",
          },
          {
            type: "formula",
            lines: ["Salary 100,000 → Needs 50,000 | Wants 30,000 | Save 20,000"],
          },
        ],
      },
      {
        id: "the-core-idea",
        heading: "Needs vs Wants",
        blocks: [
          {
            type: "p",
            text: "The hard part is honest categorisation. A need is something you can't reasonably skip — rent, utilities, groceries, transport to work. A want is everything that makes life nicer but isn't essential.",
          },
          {
            type: "table",
            head: ["Bucket", "Share", "Examples"],
            rows: [
              ["Needs", "50%", "Rent, electricity, groceries, fuel, school fees"],
              ["Wants", "30%", "Dining out, subscriptions, new phone, travel"],
              ["Save / repay", "20%", "Emergency fund, investments, extra loan payments"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "A monthly Netflix plan is a want. The internet connection you need for work sits in needs — same bill category, different purpose.",
          },
        ],
      },
      {
        id: "why-it-matters",
        heading: "Adapting It for Pakistan",
        blocks: [
          {
            type: "p",
            text: "With high inflation, many Pakistani households find needs eat well above 50%. Treat the ratios as a target to move toward, not a pass/fail test — even shifting 5% from wants to savings compounds meaningfully over years.",
          },
          {
            type: "callout",
            kind: "tip",
            text: "Automate the 20%: move it to savings or investments the day your salary lands, before you start spending.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "Under 50/30/20, how much of a PKR 80,000 salary goes to savings and debt repayment?",
        options: ["8,000", "16,000", "24,000", "40,000"],
        correct: 1,
        explanation: "20% of 80,000 = 16,000 for savings and debt repayment.",
      },
      {
        q: "Which of these belongs in the 'needs' bucket?",
        options: [
          "Weekend dining out",
          "A streaming subscription",
          "Rent and utilities",
          "An upgraded smartphone",
        ],
        correct: 2,
        explanation:
          "Rent and utilities are essential and can't reasonably be skipped — they're needs.",
      },
      {
        q: "What's the smartest way to apply the rule with high inflation?",
        options: [
          "Abandon budgeting entirely",
          "Treat the ratios as a target and improve gradually",
          "Spend the savings bucket first",
          "Put 100% into wants",
        ],
        correct: 1,
        explanation:
          "When needs exceed 50%, use the ratios as a direction to move toward rather than a strict pass/fail.",
      },
    ],
  },

  psx: {
    id: "psx",
    emoji: "🏛️",
    title: "How PSX Works",
    subtitle: "The mechanics of the Pakistan Stock Exchange",
    category: "PSX Basics",
    accent: "#00d4aa",
    duration: "9 min",
    level: "Beginner",
    type: "video",
    presets: ["What is the KSE-100?", "How do I open a CDC account?", "What are trading hours?"],
    sections: [
      {
        id: "introduction",
        heading: "What the PSX Actually Is",
        blocks: [
          {
            type: "p",
            text: "The Pakistan Stock Exchange is the marketplace where shares of listed Pakistani companies are bought and sold. When you buy a share of a company like a PSX-listed bank or fertiliser maker, you own a small slice of that business and its future profits.",
          },
          {
            type: "callout",
            kind: "note",
            text: "The KSE-100 is the benchmark index — it tracks 100 of the largest companies by market capitalisation and is the number you'll see quoted as 'the market'.",
          },
        ],
      },
      {
        id: "the-core-idea",
        heading: "How a Trade Happens",
        blocks: [
          {
            type: "p",
            text: "You can't trade directly on the exchange. You open an account with a licensed broker, who routes your order to the PSX. Your shares are held in a central electronic depository (the CDC) under your name — not physically with the broker.",
          },
          {
            type: "table",
            head: ["Step", "Who", "What happens"],
            rows: [
              ["1. Open account", "You + broker", "CDC sub-account is created in your name"],
              ["2. Place order", "You", "Buy/sell at market or a limit price"],
              ["3. Match & settle", "PSX + NCCPL", "Trade clears, settles on a T+2 basis"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "Place a limit buy for a bank stock at PKR 120. If a seller is willing at 120 or lower, the order fills; otherwise it waits in the order book.",
          },
        ],
      },
      {
        id: "why-it-matters",
        heading: "Hours, Circuit Breakers & Risk",
        blocks: [
          {
            type: "p",
            text: "PSX trades on weekdays during set hours, and individual stocks have daily price limits (circuit breakers) that cap how far they can move in one session — a mechanism designed to slow panic in a retail-heavy market.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "Retail sentiment moves PSX fast. A stock hitting its upper or lower circuit can trap you in or out of a position — size your trades accordingly.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "What does the KSE-100 measure?",
        options: [
          "The 100 cheapest stocks on PSX",
          "100 of the largest PSX companies by market capitalisation",
          "All companies listed in Pakistan",
          "Only banking sector stocks",
        ],
        correct: 1,
        explanation:
          "The KSE-100 is the benchmark index of 100 large companies, widely quoted as 'the market'.",
      },
      {
        q: "Where are your PSX shares held after you buy them?",
        options: [
          "Physically with your broker",
          "In an electronic CDC sub-account in your name",
          "At the company's head office",
          "In your bank account",
        ],
        correct: 1,
        explanation:
          "Shares sit in the Central Depository Company electronically, registered to you — not held by the broker.",
      },
      {
        q: "What is the purpose of a circuit breaker on a PSX stock?",
        options: [
          "To guarantee profits",
          "To cap how far a stock's price can move in a single session",
          "To set the dividend",
          "To open new trading accounts",
        ],
        correct: 1,
        explanation:
          "Circuit breakers limit a stock's daily price move to slow panic-driven swings.",
      },
    ],
  },

  halal: {
    id: "halal",
    emoji: "📿",
    title: "Halal Investing & Islamic Finance",
    subtitle: "Sharia-compliant principles for the modern investor",
    category: "Islamic Finance",
    accent: "#22c55e",
    duration: "8 min",
    level: "Beginner",
    type: "article",
    presets: [
      "What makes a stock halal?",
      "What is the KMI-30 index?",
      "Is interest income allowed?",
    ],
    sections: [
      {
        id: "introduction",
        heading: "What Makes Investing Halal",
        blocks: [
          {
            type: "p",
            text: "Halal investing applies Islamic principles to the stock market. The core rules: avoid riba (interest), avoid excessive gharar (uncertainty/speculation), and avoid owning businesses whose core activity is haram — such as conventional banking, alcohol, gambling, or pork.",
          },
          {
            type: "callout",
            kind: "note",
            text: "On PSX, the KMI-30 and KMI All-Share indices track companies screened as Sharia-compliant, so you don't have to vet every stock from scratch.",
          },
        ],
      },
      {
        id: "the-core-idea",
        heading: "The Screening Tests",
        blocks: [
          {
            type: "p",
            text: "A stock is screened on two levels. First, its business must be permissible. Second, its finances must pass quantitative thresholds — a company can run a halal business but still fail if it carries too much interest-based debt.",
          },
          {
            type: "table",
            head: ["Screen", "Common threshold", "Why it exists"],
            rows: [
              [
                "Interest-bearing debt ÷ assets",
                "< 37%",
                "Limits reliance on riba-based borrowing",
              ],
              ["Interest income ÷ revenue", "< 5%", "Keeps haram income immaterial"],
              ["Non-compliant investments", "Below set limit", "Avoids indirect haram exposure"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "A profitable cement maker may still fail the screen if most of its balance sheet is funded by conventional interest-bearing loans.",
          },
        ],
      },
      {
        id: "purification",
        heading: "Income Purification",
        blocks: [
          {
            type: "p",
            text: "Even compliant companies may earn a tiny share of income from interest. Scholars require investors to 'purify' this by donating the equivalent proportion of their dividends to charity, keeping the remaining return halal.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "Screening status can change as a company's debt levels shift. Re-check compliance periodically rather than assuming it's permanent.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "Which index on PSX tracks Sharia-compliant companies?",
        options: ["KSE-100", "KMI-30", "KSE-30", "BR Index"],
        correct: 1,
        explanation: "The KMI-30 (and KMI All-Share) track Sharia-screened PSX companies.",
      },
      {
        q: "A company runs a permissible business but funds itself mostly with interest-bearing loans. Is it halal to invest in?",
        options: [
          "Yes — the business activity is all that matters",
          "Not necessarily — it can fail the financial debt screen",
          "Yes — debt is never part of screening",
          "Only if it pays a dividend",
        ],
        correct: 1,
        explanation:
          "Both the business and its finances are screened. Excessive interest-based debt can disqualify a permissible business.",
      },
      {
        q: "What is 'purification' in halal investing?",
        options: [
          "Selling all stocks once a year",
          "Donating the share of returns linked to impermissible income",
          "Only buying KMI-30 stocks",
          "Avoiding dividends entirely",
        ],
        correct: 1,
        explanation:
          "Purification means giving away the proportion of income tied to non-compliant sources, such as small interest earnings.",
      },
    ],
  },

  "pe-ratio": {
    id: "pe-ratio",
    emoji: "🧮",
    title: "Understanding P/E Ratio",
    subtitle: "Judging whether a stock is cheap or expensive",
    category: "Fundamentals",
    accent: "#3b82f6",
    duration: "5 min",
    level: "Intermediate",
    type: "article",
    presets: ["What is a 'good' P/E?", "Forward vs trailing P/E?", "P/E for PSX banks?"],
    sections: [
      {
        id: "introduction",
        heading: "What the P/E Ratio Tells You",
        blocks: [
          {
            type: "p",
            text: "The price-to-earnings (P/E) ratio answers one question: how many rupees are you paying for every one rupee of a company's annual profit? A P/E of 8 means the market values the stock at 8 times its yearly earnings per share.",
          },
          {
            type: "formula",
            lines: ["P/E = Share Price ÷ Earnings Per Share (EPS)", "Example: 240 ÷ 30 = 8.0x"],
          },
          {
            type: "callout",
            kind: "note",
            text: "EPS on PSX is usually reported annually in company financials. Most terminals show trailing EPS (last 12 months) by default.",
          },
        ],
      },
      {
        id: "cheap-vs-expensive",
        heading: "Cheap Isn't Always Good",
        blocks: [
          {
            type: "p",
            text: "A low P/E can mean a bargain — or a company the market expects to shrink. A high P/E can mean an overpriced stock — or one investors expect to grow fast. The number only has meaning when you compare a company to its own sector.",
          },
          {
            type: "table",
            head: ["Stock type", "Typical PSX P/E", "What it usually signals"],
            rows: [
              ["Mature bank", "4–7x", "Steady earnings, low growth expectations"],
              ["Cement / cyclical", "6–10x", "Earnings swing with the economic cycle"],
              ["Fast-growing tech/FMCG", "15x+", "Market is pricing in future growth"],
            ],
          },
          {
            type: "callout",
            kind: "example",
            text: "If a PSX bank trades at 4x while its peers average 7x, ask why. Sometimes it's an opportunity; sometimes the market sees a risk you haven't yet.",
          },
        ],
      },
      {
        id: "limits",
        heading: "Where P/E Breaks Down",
        blocks: [
          {
            type: "p",
            text: "P/E is useless when a company has no profit (negative EPS), and it can be distorted by one-off gains like asset sales. Always check whether the earnings are recurring before trusting the ratio.",
          },
          {
            type: "callout",
            kind: "warning",
            text: "A single-year P/E can be misleading for cyclical PSX sectors. Look at earnings across a full cycle, not just the latest result.",
          },
        ],
      },
    ],
    quiz: [
      {
        q: "A stock trades at PKR 150 with an EPS of PKR 25. What is its P/E?",
        options: ["3.75x", "6.0x", "25x", "150x"],
        correct: 1,
        explanation: "P/E = price ÷ EPS = 150 ÷ 25 = 6.0x.",
      },
      {
        q: "A PSX bank has a P/E of 4 while the sector averages 7. What is the smartest read?",
        options: [
          "It is automatically a bargain — buy immediately",
          "Investigate why it's cheaper before concluding anything",
          "It is overpriced and should be avoided",
          "P/E never applies to banks",
        ],
        correct: 1,
        explanation:
          "A below-peer P/E is a prompt to investigate, not an automatic buy. The discount may reflect real risk.",
      },
      {
        q: "When is the P/E ratio least reliable?",
        options: [
          "When the company has steady recurring profits",
          "When earnings are negative or boosted by one-off gains",
          "When comparing a company to its own sector",
          "When the stock pays a dividend",
        ],
        correct: 1,
        explanation:
          "With no profit or distorted one-off earnings, P/E gives a misleading picture of value.",
      },
    ],
  },
};

export interface Flashcard {
  front: string;
  ur: string;
  def: string;
}

export const FLASHCARDS: Flashcard[] = GLOSSARY.map((t) => ({ front: t.en, ur: t.ur, def: t.def }));

export function lessonOrder(): string[] {
  return Object.keys(LESSON_ID_BY_TITLE).map((title) => LESSON_ID_BY_TITLE[title]);
}

export function xpForScore(correct: number, total: number): number {
  if (correct >= total) return 50;
  if (correct >= Math.ceil(total * 0.66)) return 30;
  if (correct >= 1) return 10;
  return 0;
}

/**
 * Safely resolve a lesson ID from a canonical English title.
 * LESSON_ID_BY_TITLE is keyed by English titles only — do NOT pass a
 * translated string here. The `LESSONS` array in `finance-data.ts`
 * holds the canonical English titles; use them directly.
 */
export function lessonId(title: string): string {
  return LESSON_ID_BY_TITLE[title];
}
