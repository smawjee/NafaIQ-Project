// App language (English / Urdu), persisted to AsyncStorage. Ported from the web
// use-lang.ts (localStorage) — the UR dictionary + translate() are verbatim; the
// store is adapted for RN (async hydrate). useLang() reads via useSyncExternalStore.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useSyncExternalStore } from "react";

export type Lang = "en" | "ur";

const STORAGE_KEY = "nafaiq-app-lang";
const listeners = new Set<() => void>();
let current: Lang = "en";

// Hydrate from storage on load, then notify subscribers.
AsyncStorage.getItem(STORAGE_KEY)
  .then((v) => {
    if (v === "ur" || v === "en") {
      current = v;
      listeners.forEach((l) => l());
    }
  })
  .catch(() => {});

function setStore(lang: Lang) {
  current = lang;
  AsyncStorage.setItem(STORAGE_KEY, lang).catch(() => {});
  listeners.forEach((l) => l());
}

/**
 * Non-hook accessor for the current language — for API clients that thread
 * `?lang=` into a request outside React (mirrors web `getCurrentLang()`).
 */
export function getCurrentLang(): Lang {
  return current;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

const UR: Record<string, string> = {
  // Nav
  Dashboard: "ڈیش بورڈ",
  "PSX Market": "پی ایس ایکس مارکیٹ",
  Portfolio: "پورٹ فولیو",
  Finance: "مالیات",
  "Learn Hub": "لرن ہب",
  Alerts: "الرٹس",
  Markets: "مارکیٹس",
  Settings: "ترتیبات",
  Profile: "پروفائل",
  "Plans / Upgrade": "پلانز / اپ گریڈ",
  Logout: "لاگ آؤٹ",
  "Sign out": "سائن آؤٹ",
  More: "مزید",
  Lesson: "سبق",
  // Header / common
  "Upgrade to Pro": "پرو میں اپ گریڈ کریں",
  "Free plan": "مفت پلان",
  Home: "ہوم",
  Learn: "سیکھیں",
  // Settings page
  "Personalise how NafaIQ looks and feels.": "نفع آئی کیو کی شکل و صورت کو اپنی پسند کے مطابق بنائیں۔",
  Appearance: "ظاہری شکل",
  "Choose the theme for your dashboard. This applies to the app only — the public site stays dark.":
    "اپنے ڈیش بورڈ کے لیے تھیم منتخب کریں۔ یہ صرف ایپ پر لاگو ہوتا ہے — عوامی سائٹ تاریک رہتی ہے۔",
  Dark: "تاریک",
  Light: "روشن",
  "Default OLED-friendly terminal look": "ڈیفالٹ OLED دوست ٹرمینل لُک",
  "Bright, high-contrast daytime view": "روشن، ہائی کنٹراسٹ دن کا منظر",
  Language: "زبان",
  "Choose the language for the app interface.": "ایپ انٹرفیس کے لیے زبان منتخب کریں۔",
  English: "انگریزی",
  Urdu: "اردو",
  "Standard interface language": "معیاری انٹرفیس زبان",
  "Right-to-left Urdu interface": "دائیں سے بائیں اردو انٹرفیس",
  Account: "اکاؤنٹ",
  Name: "نام",
  Email: "ای میل",
  Plan: "پلان",

  // Settings → change password
  Password: "پاس ورڈ",
  "Changing your password signs you out everywhere else.":
    "پاس ورڈ تبدیل کرنے سے آپ ہر دوسری جگہ سے سائن آؤٹ ہو جائیں گے۔",
  "Current password": "موجودہ پاس ورڈ",
  "New password": "نیا پاس ورڈ",
  "Confirm new password": "نئے پاس ورڈ کی تصدیق کریں",
  "Update password": "پاس ورڈ اپ ڈیٹ کریں",
  "Current password is incorrect.": "موجودہ پاس ورڈ غلط ہے۔",
  "Password must be at least 8 characters.":
    "پاس ورڈ کم از کم 8 حروف کا ہونا چاہیے۔",
  "Those passwords don't match.": "یہ پاس ورڈ آپس میں مطابقت نہیں رکھتے۔",
  "Your new password must be different from your current one.":
    "آپ کا نیا پاس ورڈ موجودہ پاس ورڈ سے مختلف ہونا چاہیے۔",
  "Could not update password": "پاس ورڈ اپ ڈیٹ نہیں ہو سکا",
  "Password updated. Other devices have been signed out.":
    "پاس ورڈ اپ ڈیٹ ہو گیا۔ دیگر آلات سے سائن آؤٹ کر دیا گیا ہے۔",

  // ---- Shared stat / metric labels ----
  "Portfolio Value": "پورٹ فولیو ویلیو",
  "Total Invested": "کل سرمایہ کاری",
  "Total Gain": "کل منافع",
  "Today's P/L": "آج کا نفع/نقصان",
  "Today's PSX P/L": "آج کا پی ایس ایکس نفع/نقصان",
  "Monthly Spending": "ماہانہ اخراجات",
  "Total Net Worth": "کل مجموعی مالیت",
  "Monthly Income": "ماہانہ آمدنی",
  "Total Expenses": "کل اخراجات",
  "Net Savings": "خالص بچت",
  "Savings Rate": "بچت کی شرح",

  // ---- Dashboard ----
  "Explore PSX": "پی ایس ایکس دیکھیں",
  "Add Transaction": "ٹرانزیکشن شامل کریں",
  "AI Recommendation": "اے آئی تجویز",
  View: "دیکھیں",
  Dismiss: "نظر انداز کریں",
  "Spending Breakdown": "اخراجات کی تفصیل",
  Watchlist: "واچ لسٹ",
  "Savings Goals": "بچت کے اہداف",
  "PKR total": "کل روپے",

  // ---- Portfolio ----
  "Performance vs KSE-100": "کارکردگی بمقابلہ کے ایس ای-100",
  "Outperforming benchmark by +3.2%": "بینچ مارک سے +3.2% بہتر کارکردگی",
  "Haqeeqi Daulat™ — Your REAL Returns": "حقیقی دولت™ — آپ کا اصل منافع",
  "After 16.2% PKR devaluation": "16.2% روپے کی قدر میں کمی کے بعد",
  "Nominal PKR Gain": "برائے نام روپے منافع",
  "PKR Devaluation": "روپے کی قدر میں کمی",
  "Real USD Return": "اصل ڈالر منافع",
  "Devaluation Shield Score": "قدر کمی شیلڈ اسکور",
  "Moderate risk": "درمیانہ خطرہ",
  "Improve Score": "اسکور بہتر بنائیں",
  "Allocation by Sector": "شعبے کے لحاظ سے تقسیم",
  "Allocation by Stock": "اسٹاک کے لحاظ سے تقسیم",
  Holdings: "ملکیتی اسٹاکس",
  Stock: "اسٹاک",
  Sector: "شعبہ",
  Shares: "حصص",
  "Avg Cost": "اوسط لاگت",
  Current: "موجودہ",
  "Mkt Value": "مارکیٹ ویلیو",
  "Gain/Loss": "نفع/نقصان",
  Signal: "سگنل",
  Action: "ایکشن",
  "Add Holding": "ہولڈنگ شامل کریں",
  "Edit Holding": "ہولڈنگ میں ترمیم کریں",
  "Save Changes": "تبدیلیاں محفوظ کریں",
  Edit: "ترمیم",
  Delete: "حذف کریں",
  "No holdings yet. Add your first position.": "ابھی کوئی ہولڈنگ نہیں۔ اپنی پہلی پوزیشن شامل کریں۔",
  "Stock symbol (e.g. HBL)": "اسٹاک علامت (مثلاً HBL)",
  "Avg Cost (PKR)": "اوسط لاگت (روپے)",
  "Current price (PKR, optional)": "موجودہ قیمت (روپے، اختیاری)",
  "Please enter a stock symbol.": "براہ کرم اسٹاک علامت درج کریں۔",
  "Please enter a sector.": "براہ کرم شعبہ درج کریں۔",
  "Please enter a valid number of shares.": "براہ کرم درست تعداد میں حصص درج کریں۔",
  "Please enter a valid average cost.": "براہ کرم درست اوسط لاگت درج کریں۔",
  "AI Portfolio Report": "اے آئی پورٹ فولیو رپورٹ",
  "Get a plain-English analysis — diversification score, risk assessment, top opportunities, and suggested rebalancing.":
    "سادہ زبان میں تجزیہ حاصل کریں — تنوع اسکور، خطرے کا جائزہ، بہترین مواقع اور تجویز کردہ ری بیلنسنگ۔",
  "Generate Report": "رپورٹ بنائیں",
  "Analyzing…": "تجزیہ ہو رہا ہے…",
  "Health Score": "ہیلتھ اسکور",
  "Export as PDF": "پی ڈی ایف ایکسپورٹ کریں",
  Close: "بند کریں",

  // ---- PSX ----
  "Stock Screener": "اسٹاک اسکرینر",
  Price: "قیمت",
  Change: "تبدیلی",
  Volume: "حجم",
  "Mkt Cap": "مارکیٹ کیپ",
  "Sector Heatmap": "سیکٹر ہیٹ میپ",
  "Add Stock": "اسٹاک شامل کریں",

  // ---- Finance ----
  "Saved this month": "اس ماہ بچایا",
  "Personal Finance": "ذاتی مالیات",
  Overview: "جائزہ",
  Transactions: "ٹرانزیکشنز",
  Budgets: "بجٹ",
  Bills: "بل",
  Goals: "اہداف",
  "Net Savings Rate": "خالص بچت کی شرح",

  // ---- Alerts ----
  "Active Alerts": "فعال الرٹس",
  "Add New Alert": "نیا الرٹ شامل کریں",
  Above: "اوپر",
  Below: "نیچے",
  "Notification History": "اطلاعات کی تاریخ",
  "Stock Price": "اسٹاک کی قیمت",
  "Bill Reminder": "بل یاد دہانی",
  Budget: "بجٹ",
  "Goal Milestone": "ہدف سنگ میل",
  "Create Alert": "الرٹ بنائیں",
  Push: "پش",

  // ---- Common / shell ----
  today: "آج",
  "Asalam-o-Alaikum,": "السلام علیکم،",
  Live: "لائیو",
  Notifications: "اطلاعات",
  "View all": "سب دیکھیں",
  Free: "مفت",
  plan: "پلان",
  "Search stocks (e.g. HBL)…": "اسٹاکس تلاش کریں (مثلاً HBL)…",
  "Search stocks": "اسٹاکس تلاش کریں",
  "Search transactions": "ٹرانزیکشنز تلاش کریں",
  "Search terms": "اصطلاحات تلاش کریں",
  Indicator: "اشارہ",
  Value: "قدر",
  Reading: "ریڈنگ",
  Neutral: "غیر جانبدار",
  Overbought: "اوور باٹ",
  Oversold: "اوور سولڈ",

  // ---- Signals ----
  "STRONG BUY": "اسٹرانگ بائی",
  BUY: "بائی",
  HOLD: "ہولڈ",
  SELL: "سیل",
  "STRONG SELL": "اسٹرانگ سیل",
  // ---- Calibrated recommendation (SignalRecommendationCard) ----
  Recommendation: "سفارش",
  "Strong Buy": "مضبوط خریداری",
  Buy: "خریدیں",
  Hold: "روکیں",
  Sell: "فروخت کریں",
  "Strong Sell": "مضبوط فروخت",
  "Based on": "بنیاد",
  "comparable cases in PSX history": "پی ایس ایکس تاریخ میں ملتے جلتے واقعات",
  "rose over the next 20 trading sessions": "اگلے 20 ٹریڈنگ سیشنز میں اوپر گئے",
  vs: "بمقابلہ",
  typical: "عام",
  Range: "حد",
  "95% confidence": "95% اعتماد",
  "Measured across": "پیمائش کی گئی",
  "Est. round-trip cost": "تخمینی مکمل لین دین لاگت",
  "Suggested stop": "تجویز کردہ اسٹاپ",
  "The historical range for this setup spans the market average, so there is no clear edge either way.":
    "اس سیٹ اپ کی تاریخی حد مارکیٹ اوسط پر محیط ہے، اس لیے کسی بھی طرف واضح برتری نہیں۔",
  "This setup leaned slightly one way historically, but not by enough to cover trading costs.":
    "یہ سیٹ اپ تاریخی طور پر ہلکا سا ایک طرف جھکا، مگر ٹریڈنگ لاگت پوری کرنے کے لیے کافی نہیں۔",
  "Too few comparable cases in PSX history to say anything reliable.":
    "پی ایس ایکس تاریخ میں اتنے کم ملتے جلتے واقعات ہیں کہ قابلِ اعتماد بات نہیں کہی جا سکتی۔",
  "Historical base rates are unavailable right now.":
    "تاریخی بنیادی شرحیں فی الحال دستیاب نہیں۔",
  "No clear edge in the historical record.": "تاریخی ریکارڈ میں کوئی واضح برتری نہیں۔",
  "Indicators currently read": "اشاریے فی الحال بتا رہے ہیں",
  ", but this is about what happened next: on PSX, stocks in this state went on to rise":
    "، مگر یہ اس بارے میں ہے کہ آگے کیا ہوا: پی ایس ایکس پر اس حالت والے اسٹاکس آگے چل کر اوپر گئے",
  "of the time over the following": "اوقات میں، اگلے",
  "sessions. Measured, not a promise.": "سیشنز میں۔ پیمائش شدہ، وعدہ نہیں۔",
  "Buy calls require stronger evidence than sell calls — on PSX the sell-side signal has historically been the more reliable of the two.":
    "خریداری کی سفارشات کو فروخت کی نسبت زیادہ مضبوط شواہد درکار ہیں — پی ایس ایکس پر فروخت کا سگنل تاریخی طور پر زیادہ قابلِ اعتماد رہا ہے۔",
  All: "تمام",
  Gainers: "بڑھنے والے",
  Losers: "گھٹنے والے",
  "Most Active": "سب سے فعال",

  // ---- Sectors ----
  Banking: "بینکنگ",
  Cement: "سیمنٹ",
  "Oil & Gas": "آئل اینڈ گیس",
  Fertilizer: "فرٹیلائزر",
  Textile: "ٹیکسٹائل",
  Power: "پاور",
  Pharma: "فارما",
  Tech: "ٹیک",
  Auto: "آٹو",

  // ---- Spending categories ----
  Food: "کھانا",
  Utilities: "یوٹیلیٹیز",
  Transport: "ٹرانسپورٹ",
  Shopping: "شاپنگ",
  Other: "دیگر",
  "Food & Dining": "کھانا اور ڈائننگ",
  Groceries: "گروسری",
  Subscriptions: "سبسکرپشنز",
  Savings: "بچت",
  Income: "آمدنی",
  Expense: "اخراجات",

  // ---- Dashboard ----
  "Redirect PKR 5,000 from dining to your Hajj Fund.":
    "کھانے سے PKR 5,000 اپنے حج فنڈ کی طرف منتقل کریں۔",
  "You spent 15% more on dining this month — reallocating brings your goal 3 months closer. HBL is also flashing a Strong Buy, up 2.41% on rising volume.":
    "آپ نے اس ماہ کھانے پر 15% زیادہ خرچ کیا — دوبارہ تقسیم آپ کے ہدف کو 3 ماہ قریب لے آتی ہے۔ HBL بھی اسٹرانگ بائی دکھا رہا ہے، بڑھتے حجم پر 2.41% اوپر۔",

  // ---- Goal names + AI advice ----
  "Hajj Fund": "حج فنڈ",
  "Emergency Fund": "ایمرجنسی فنڈ",
  "Honda City": "ہونڈا سٹی",
  "Umrah 2026": "عمرہ 2026",
  "At PKR 25,000/month you'll reach this goal in 31 months. June dining overspend delayed this by ~6 days.":
    "PKR 25,000 ماہانہ پر آپ یہ ہدف 31 ماہ میں حاصل کر لیں گے۔ جون میں کھانے کے زیادہ اخراجات نے اسے ~6 دن مؤخر کر دیا۔",
  "Almost there! PKR 120,000 remaining. At current rate: 5 months.":
    "تقریباً پہنچ گئے! PKR 120,000 باقی ہیں۔ موجودہ رفتار پر: 5 ماہ۔",
  "This goal needs attention. Consider increasing monthly contribution by PKR 5,000.":
    "اس ہدف پر توجہ درکار ہے۔ ماہانہ رقم میں PKR 5,000 اضافے پر غور کریں۔",
  "You need to save PKR 15,833/month to reach this goal by your target.":
    "ہدف تک پہنچنے کے لیے آپ کو PKR 15,833 ماہانہ بچانا ہوگا۔",

  // ---- Finance ----
  "6-Month Overview": "6 ماہ کا جائزہ",
  In: "آمد",
  Out: "اخراج",
  "Add Bill": "بل شامل کریں",
  "Add Goal": "ہدف شامل کریں",
  "Amount (PKR)": "رقم (روپے)",
  "Please enter a valid amount.": "براہ کرم درست رقم درج کریں۔",
  Due: "واجب الادا",
  "Target date:": "ہدف کی تاریخ:",
  Target: "ہدف",
  Saved: "بچایا",
  "DUE SOON": "جلد واجب",
  UPCOMING: "آنے والا",
  "SNGPL Gas": "ایس این جی پی ایل گیس",
  "PTCL Internet": "پی ٹی سی ایل انٹرنیٹ",
  "Apartment Rent": "اپارٹمنٹ کرایہ",
  "Credit Card": "کریڈٹ کارڈ",
  "You've exceeded your dining budget by PKR 3,000. This is delaying your Hajj Fund goal by approximately 6 days.":
    "آپ نے کھانے کا بجٹ PKR 3,000 سے تجاوز کر لیا ہے۔ یہ آپ کے حج فنڈ ہدف کو تقریباً 6 دن مؤخر کر رہا ہے۔",
  "Shopping is PKR 3,050 over budget. Trimming this next month frees up cash for your Emergency Fund.":
    "شاپنگ بجٹ سے PKR 3,050 زیادہ ہے۔ اگلے ماہ اسے کم کرنے سے آپ کے ایمرجنسی فنڈ کے لیے رقم بچے گی۔",

  // ---- Alerts data ----
  "Stock Price Alert": "اسٹاک قیمت الرٹ",
  "Budget Alert": "بجٹ الرٹ",
  "HBL above PKR 150": "HBL، PKR 150 سے اوپر",
  "SNGPL Gas due in 3 days": "ایس این جی پی ایل گیس 3 دن میں واجب",
  "Food & Dining 80% of budget": "کھانا اور ڈائننگ بجٹ کا 80%",
  "Hajj Fund 50% reached": "حج فنڈ 50% مکمل",
  "LUCK below PKR 800": "LUCK، PKR 800 سے نیچے",
  "Created Jun 10": "10 جون کو بنایا",
  "Created Jun 12": "12 جون کو بنایا",
  "Recurring monthly": "ماہانہ تکرار",
  "June 2025": "جون 2025",
  "One-time": "ایک بار",
  "1 day before": "1 دن پہلے",
  "3 days before": "3 دن پہلے",
  "7 days before": "7 دن پہلے",
  "HBL crossed above MA50 — Strong Buy signal triggered":
    "HBL نے MA50 عبور کر لیا — اسٹرانگ بائی سگنل فعال",
  "K-Electric bill due in 3 days — PKR 18,420":
    "کے-الیکٹرک بل 3 دن میں واجب — PKR 18,420",
  "Food & Dining budget 92% used — PKR 32,340 of 35,000":
    "کھانا اور ڈائننگ بجٹ کا 92% استعمال — 35,000 میں سے PKR 32,340",
  "Great news! Emergency Fund reached 60% of target":
    "خوشخبری! ایمرجنسی فنڈ ہدف کے 60% تک پہنچ گیا",

  // ---- PSX ----
  "KSE-100 Index": "کے ایس ای-100 انڈیکس",
  "AI Analysis": "اے آئی تجزیہ",
  "KSE-100 is trading above both MA20 and MA50 with strong volume confirmation. RSI at 58 — bullish momentum without being overbought. Banking and Tech sectors leading gains today.":
    "کے ایس ای-100 مضبوط حجم کی تصدیق کے ساتھ MA20 اور MA50 دونوں سے اوپر ٹریڈ کر رہا ہے۔ RSI 58 پر — اوور باٹ ہوئے بغیر تیزی کی رفتار۔ بینکنگ اور ٹیک شعبے آج برتری میں ہیں۔",
  "Based on technical indicators only. Not financial advice.":
    "صرف تکنیکی اشاروں کی بنیاد پر۔ مالی مشورہ نہیں۔",
  "Pakistan Stock Exchange's benchmark index — tracks the 100 largest companies by market cap. The headline number quoted as 'the market'.":
    "پاکستان اسٹاک ایکسچینج کا بینچ مارک انڈیکس — مارکیٹ کیپ کے لحاظ سے 100 سب سے بڑی کمپنیوں کو ٹریک کرتا ہے۔ یہی نمبر 'مارکیٹ' کے طور پر پیش کیا جاتا ہے۔",
  "Tracks the 30 most liquid, large companies on the PSX using a free-float methodology — a snapshot of blue-chip performance.":
    "فری-فلوٹ طریقہ کار سے PSX کی 30 سب سے زیادہ لیکویڈ، بڑی کمپنیوں کو ٹریک کرتا ہے — بلیو چپ کارکردگی کا منظر۔",
  "The KSE-Meezan Index — 30 Sharia-compliant (Islamic) companies, screened to exclude interest-based and non-permissible businesses.":
    "کے ایس ای-میزان انڈیکس — 30 شریعت کے مطابق (اسلامی) کمپنیاں، جو سودی اور ناجائز کاروبار کو خارج کر کے منتخب کی گئی ہیں۔",
  "Captures every eligible listed company on the PSX — the broadest measure of the whole market's direction.":
    "PSX کی ہر اہل لسٹڈ کمپنی کو شامل کرتا ہے — پوری مارکیٹ کی سمت کا سب سے وسیع پیمانہ۔",

  // ---- Learn Hub ----
  "From KSE basics to technical analysis — in plain Urdu and English.":
    "کے ایس ای کی بنیادی باتوں سے تکنیکی تجزیے تک — سادہ اردو اور انگریزی میں۔",
  "Beginner Investor": "ابتدائی سرمایہ کار",
  "Learning Paths": "سیکھنے کے راستے",
  "Follow a structured track or explore freely": "ایک منظم راستہ اپنائیں یا آزادانہ دریافت کریں",
  Lessons: "اسباق",
  Glossary: "لغت",
  "Flashcard Mode": "فلیش کارڈ موڈ",
  Flashcards: "فلیش کارڈز",
  "Continue Path": "راستہ جاری رکھیں",
  "Start Path": "راستہ شروع کریں",
  "Video + Article": "ویڈیو + مضمون",
  Article: "مضمون",
  "In Progress": "جاری",
  "Tap to flip": "پلٹنے کے لیے ٹیپ کریں",
  "Got it": "سمجھ گیا",
  "Review Again": "دوبارہ دیکھیں",
  "Ask AI Tutor": "اے آئی ٹیوٹر سے پوچھیں",
  "Ask AI": "اے آئی سے پوچھیں",
  "Thinking…": "سوچ رہا ہے…",
  // NafaIQ Assistant (ported from web lang-ur.ts; "Shares", "Amount (PKR)" and
  // "Powered by AI" already exist earlier in this dictionary)
  "NafaIQ Assistant": "نفع آئی کیو اسسٹنٹ",
  "Manage Plan": "پلان منظم کریں",
  "Hi! I can add transactions, track bills and goals, manage your portfolio and watchlist, and answer questions about your money. Type or tap the mic.":
    "سلام! میں ٹرانزیکشنز شامل کر سکتا ہوں، بلز اور اہداف پر نظر رکھ سکتا ہوں، آپ کا پورٹ فولیو اور واچ لسٹ سنبھال سکتا ہوں، اور آپ کے پیسوں سے متعلق سوالات کے جواب دے سکتا ہوں۔ لکھیں یا مائیک دبائیں۔",
  "Ask or tell me what to do…": "پوچھیں یا بتائیں کیا کرنا ہے…",
  "Message the assistant": "اسسٹنٹ کو پیغام بھیجیں",
  "Sign in to use NafaIQ Assistant": "نفع آئی کیو اسسٹنٹ استعمال کرنے کے لیے سائن ان کریں",
  "Daily assistant limit reached — it resets tomorrow.":
    "آج کی اسسٹنٹ حد مکمل ہو گئی — یہ کل دوبارہ سیٹ ہو جائے گی۔",
  "Add transaction of 1200 for food via Meezan card":
    "میزان کارڈ سے کھانے کی 1200 کی ٹرانزیکشن شامل کریں",
  "How much did I spend this month?": "میں نے اس مہینے کتنا خرچ کیا؟",
  "Alert me when any goal reaches 50%": "کسی بھی ہدف کے 50% پہنچنے پر مجھے اطلاع دیں",
  "Add MEBL to my watchlist": "MEBL کو میری واچ لسٹ میں شامل کریں",
  // Voice input
  "Speak your command": "اپنا حکم بولیں",
  "Stop recording": "ریکارڈنگ روکیں",
  "Could not start recording": "ریکارڈنگ شروع نہیں ہو سکی",
  "Microphone access was blocked. Enable it in your device settings.":
    "مائیکروفون تک رسائی بلاک ہے۔ اسے اپنے آلے کی ترتیبات میں فعال کریں۔",
  "I couldn't hear anything. Try again.": "مجھے کچھ سنائی نہیں دیا۔ دوبارہ کوشش کریں۔",
  "Transcription failed": "تحریر میں تبدیلی ناکام",
  // Action confirmation card
  "Add transaction": "ٹرانزیکشن شامل کریں",
  "Add bill": "بل شامل کریں",
  "Create savings goal": "بچت کا ہدف بنائیں",
  "Add to goal": "ہدف میں شامل کریں",
  "Add holding": "ہولڈنگ شامل کریں",
  "Record trade": "ٹریڈ ریکارڈ کریں",
  "Add goal alert": "ہدف کا الرٹ شامل کریں",
  "Add price alert": "قیمت کا الرٹ شامل کریں",
  "Add to watchlist": "واچ لسٹ میں شامل کریں",
  "Remove from watchlist": "واچ لسٹ سے ہٹائیں",
  Merchant: "دکاندار",
  Symbol: "علامت",
  "Target (PKR)": "ہدف (روپے)",
  "Already saved (PKR)": "پہلے سے جمع شدہ (روپے)",
  "Average cost (PKR)": "اوسط لاگت (روپے)",
  "Price (PKR)": "قیمت (روپے)",
  "Fees (PKR)": "فیس (روپے)",
  "Paid via": "ادائیگی بذریعہ",
  "Due date": "آخری تاریخ",
  "Target date": "ہدف کی تاریخ",
  "Alert at (%)": "الرٹ اس فیصد پر (%)",
  "When price is": "جب قیمت ہو",
  Quantity: "مقدار",
  Side: "قسم",
  Bill: "بل",
  Goal: "ہدف",
  Note: "نوٹ",
  expense: "خرچ",
  income: "آمدنی",
  buy: "خریداری",
  sell: "فروخت",
  above: "سے اوپر",
  below: "سے نیچے",
  "Still needed": "ابھی درکار ہے",
  Confirm: "تصدیق کریں",
  Done: "مکمل",
  "Something went wrong": "کچھ غلط ہو گیا",
  "Lesson not found": "سبق نہیں ملا",
  "Back to Learn Hub": "لرن ہب پر واپس",
  "In This Lesson": "اس سبق میں",
  "Bookmark Lesson": "سبق بک مارک کریں",
  Bookmarked: "بک مارک شدہ",
  Beginner: "ابتدائی",
  Intermediate: "درمیانہ",
  Complete: "مکمل",
  Locked: "مقفل",
  "PSX Investor Starter": "PSX سرمایہ کار آغاز",
  "From zero to your first trade": "صفر سے آپ کی پہلی ٹریڈ تک",
  "Technical Analysis": "تکنیکی تجزیہ",
  "Charts, patterns, and indicators": "چارٹس، پیٹرنز اور اشارے",
  "Islamic Finance": "اسلامی مالیات",
  "Halal investing principles": "حلال سرمایہ کاری کے اصول",
  "Budget, save, and grow": "بجٹ بنائیں، بچائیں اور بڑھائیں",
  "What is a Candlestick?": "کینڈل اسٹک کیا ہے؟",
  "Understanding RSI": "آر ایس آئی کو سمجھنا",
  "Sector Heatmap Guide": "سیکٹر ہیٹ میپ گائیڈ",
  "What is a Stop-Loss?": "اسٹاپ لاس کیا ہے؟",
  "Dividend Yield": "ڈیویڈنڈ یِلڈ",
  "5 Candle Patterns": "5 کینڈل پیٹرنز",
  "50/30/20 Budget Rule": "50/30/20 بجٹ اصول",
  "How PSX Works": "PSX کیسے کام کرتا ہے",
  "Halal Investing & Islamic Finance": "حلال سرمایہ کاری اور اسلامی مالیات",
  "Understanding P/E Ratio": "قیمت آمدنی تناسب کو سمجھنا",

  // ---- Plans ----
  "Enter App": "ایپ میں داخل ہوں",
  "Simple, honest pricing": "سادہ، ایماندار قیمتیں",
  "Start free. Upgrade when you're ready for real-time data and unlimited AI insights.":
    "مفت شروع کریں۔ جب آپ ریئل ٹائم ڈیٹا اور لامحدود اے آئی بصیرت کے لیے تیار ہوں تو اپ گریڈ کریں۔",
  Monthly: "ماہانہ",
  Yearly: "سالانہ",
  "SAVE 20%": "20% بچائیں",
  "MOST POPULAR": "سب سے مقبول",
  "/ mo": "/ ماہ",
  "Billed annually — 20% off": "سالانہ بل — 20% رعایت",
  "Compare plans": "پلانز کا موازنہ",
  Feature: "خصوصیت",
  Pro: "پرو",
  Premium: "پریمیم",
  Custom: "حسبِ ضرورت",
  "Get Started": "شروع کریں",
  "Contact Us": "ہم سے رابطہ کریں",
  "Get started with the essentials": "بنیادی چیزوں کے ساتھ آغاز کریں",
  "For serious investors": "سنجیدہ سرمایہ کاروں کے لیے",
  "For families & power users": "خاندانوں اور پاور صارفین کے لیے",
  "Delayed PSX data": "تاخیر سے PSX ڈیٹا",
  "1 portfolio": "1 پورٹ فولیو",
  "Basic finance tracker": "بنیادی فنانس ٹریکر",
  "Zakat calculator": "زکوٰۃ کیلکولیٹر",
  "3 AI Advisor queries / month": "3 اے آئی ایڈوائزر سوالات / ماہ",
  "Real-time PSX data": "ریئل ٹائم PSX ڈیٹا",
  "Unlimited AI Advisor": "لامحدود اے آئی ایڈوائزر",
  "Full Haqeeqi Daulat breakdown": "مکمل حقیقی دولت تفصیل",
  "Unlimited portfolios & watchlists": "لامحدود پورٹ فولیوز اور واچ لسٹس",
  "Halal screening filters": "حلال اسکریننگ فلٹرز",
  "Priority alerts": "ترجیحی الرٹس",
  "Everything in Pro": "پرو کی ہر چیز",
  "Multi-account / family tracking": "ملٹی اکاؤنٹ / فیملی ٹریکنگ",
  "Advanced data export": "ایڈوانس ڈیٹا ایکسپورٹ",
  "Priority support": "ترجیحی سپورٹ",

  // ---- Stock detail ----
  "Back to Market": "مارکیٹ پر واپس",
  "AI Technical Analysis": "اے آئی تکنیکی تجزیہ",
  "Recent News": "حالیہ خبریں",
  "Add to Watchlist": "واچ لسٹ میں شامل کریں",
  "Add to Portfolio": "پورٹ فولیو میں شامل کریں",
  "Set Price Alert": "قیمت الرٹ سیٹ کریں",
  "Market Cap": "مارکیٹ کیپ",
  "P/E Ratio": "قیمت آمدنی تناسب",
  EPS: "ای پی ایس",
  "52W High": "52 ہفتہ بلند",
  "52W Low": "52 ہفتہ کم",
  "Avg Volume": "اوسط حجم",
  "Book Value": "بک ویلیو",
  "This is AI-generated technical analysis only. Not financial advice.":
    "یہ صرف اے آئی سے تیار کردہ تکنیکی تجزیہ ہے۔ مالی مشورہ نہیں۔",

  // ---- Portfolio report + misc ----
  "— AI signals suggest reviewing these positions.":
    "— اے آئی سگنلز ان پوزیشنز کا جائزہ لینے کی تجویز دیتے ہیں۔",
  "Your Portfolio Report — June 2025": "آپ کی پورٹ فولیو رپورٹ — جون 2025",
  "Diversification Analysis": "تنوع کا تجزیہ",
  "Risk Assessment": "خطرے کا جائزہ",
  Opportunities: "مواقع",
  "Suggested Actions": "تجویز کردہ اقدامات",
  "Your portfolio is moderately diversified across 4 sectors. However, Oil & Gas represents 34% of your holdings which increases sector concentration risk. Consider adding a Tech or FMCG stock to balance exposure.":
    "آپ کا پورٹ فولیو 4 شعبوں میں معتدل طور پر متنوع ہے۔ تاہم، آئل اینڈ گیس آپ کی ملکیت کا 34% ہے جو شعبہ ارتکاز کا خطرہ بڑھاتا ہے۔ توازن کے لیے ایک ٹیک یا ایف ایم سی جی اسٹاک شامل کرنے پر غور کریں۔",
  "Medium risk profile. FFC is showing a SELL signal with RSI at 38 — consider reviewing this position. LUCK (HOLD) is underperforming vs sector avg.":
    "درمیانہ خطرہ پروفائل۔ FFC، RSI 38 کے ساتھ سیل سگنل دکھا رہا ہے — اس پوزیشن کا جائزہ لیں۔ LUCK (ہولڈ) شعبے کی اوسط کے مقابلے میں کمزور کارکردگی دکھا رہا ہے۔",
  "HBL and UBL in the Banking sector are both showing Strong Buy signals. Your existing HBL position is +20.4% — consider whether to take partial profits.":
    "بینکنگ شعبے میں HBL اور UBL دونوں اسٹرانگ بائی سگنل دکھا رہے ہیں۔ آپ کی موجودہ HBL پوزیشن +20.4% ہے — جزوی منافع لینے پر غور کریں۔",
  "1. Review FFC position (SELL signal active)\n2. Consider reducing Oil & Gas concentration below 25%\n3. HBL approaching resistance at 150 — set a price alert":
    "1۔ FFC پوزیشن کا جائزہ لیں (سیل سگنل فعال)\n2۔ آئل اینڈ گیس ارتکاز 25% سے کم کرنے پر غور کریں\n3۔ HBL، 150 پر مزاحمت کے قریب — قیمت الرٹ سیٹ کریں",
  "34% of portfolio in Oil & Gas provides partial hedge against rupee weakness.":
    "پورٹ فولیو کا 34% آئل اینڈ گیس میں روپے کی کمزوری کے خلاف جزوی تحفظ فراہم کرتا ہے۔",
  "BULLISH · Confidence 72%": "تیزی · اعتماد 72%",

  // ---- Learn Hub (extended) ----
  "lessons complete": "اسباق مکمل",
  "5 Day Streak": "5 دن کا تسلسل",
  "Lessons Done": "اسباق مکمل",
  "XP Earned": "ایکس پی حاصل",
  "Beginner Level": "ابتدائی سطح",
  lessons: "اسباق",
  "Est:": "تخمینہ:",
  min: "منٹ",
  "complete": "مکمل",
  "No terms found for": "کوئی اصطلاح نہیں ملی",
  "Deck Complete!": "ڈیک مکمل!",
  "You reviewed all": "آپ نے تمام",
  terms: "اصطلاحات",
  "terms.": "اصطلاحات کا جائزہ لیا۔",
  "Restart Deck": "ڈیک دوبارہ شروع کریں",
  Exit: "باہر نکلیں",
  "Ask about investing…": "سرمایہ کاری کے بارے میں پوچھیں…",
  "What is the KSE-100 index?": "کے ایس ای-100 انڈیکس کیا ہے؟",
  "How do I start investing in PSX?": "میں پی ایس ایکس میں سرمایہ کاری کیسے شروع کروں؟",
  "Explain candlestick charts simply": "کینڈل اسٹک چارٹس آسان الفاظ میں سمجھائیں",
  "Hi! I'm your NafaIQ tutor. Ask me anything about PSX investing, terms, or strategies.":
    "سلام! میں آپ کا نفع آئی کیو ٹیوٹر ہوں۔ پی ایس ایکس سرمایہ کاری، اصطلاحات یا حکمت عملی کے بارے میں کچھ بھی پوچھیں۔",
  "Sorry, something went wrong. Please try again.":
    "معذرت، کچھ غلط ہو گیا۔ براہ کرم دوبارہ کوشش کریں۔",

  // ---- Lesson page ----
  Bookmark: "بک مارک",
  read: "پڑھنے کا وقت",
  Hide: "چھپائیں",
  Read: "پڑھیں",
  "Article Version": "مضمون ورژن",
  "Mark Video as Watched": "ویڈیو کو دیکھا ہوا نشان زد کریں",
  "Watch at least 80% of the video to mark as complete":
    "مکمل کے طور پر نشان زد کرنے کے لیے کم از کم 80% ویڈیو دیکھیں",
  "Test Your Understanding — Take the Quiz":
    "اپنی سمجھ بوجھ آزمائیں — کوئز دیں",
  questions: "سوالات",
  "Earn up to 50 XP": "50 ایکس پی تک حاصل کریں",
  "You've completed this lesson": "آپ نے یہ سبق مکمل کر لیا ہے",
  Previous: "پچھلا",
  Next: "اگلا",
  "Video loading…": "ویڈیو لوڈ ہو رہی ہے…",
  "Back to Lesson": "سبق پر واپس",
  "Up to 50 XP": "50 ایکس پی تک",
  "Knowledge Check": "علم کی جانچ",
  Question: "سوال",
  of: "میں سے",
  "Correct! ": "درست! ",
  "Not quite. ": "بالکل نہیں۔ ",
  "See Results": "نتائج دیکھیں",
  "Next Question": "اگلا سوال",
  "Quiz Results": "کوئز کے نتائج",
  "Added to your profile": "آپ کے پروفائل میں شامل",
  "XP total": "کل ایکس پی",
  "Continue Learning": "سیکھنا جاری رکھیں",
  "Retake Quiz": "کوئز دوبارہ دیں",
  "Perfect Score! Ustād level understanding!":
    "بہترین اسکور! استاد جیسی سمجھ بوجھ!",
  "Great work! One more review and you'll nail it.":
    "بہترین کام! ایک اور جائزہ اور آپ کامیاب!",
  "📖 Keep learning — review the lesson and retry.":
    "📖 سیکھتے رہیں — سبق کا جائزہ لیں اور دوبارہ کوشش کریں۔",
  "💪 Don't give up — re-read and try again!":
    "💪 ہمت نہ ہاریں — دوبارہ پڑھیں اور کوشش کریں!",
  "AI Tutor": "اے آئی ٹیوٹر",
  "Ask anything about this lesson": "اس سبق کے بارے میں کچھ بھی پوچھیں",
  "Powered by AI": "اے آئی سے چلایا گیا",
  "just now": "ابھی",
  "Ask about this lesson…": "اس سبق کے بارے میں پوچھیں…",
  "Hi! I'm here to help you understand": "سلام! میں آپ کی مدد کے لیے حاضر ہوں",
  "What would you like to know?": "آپ کیا جاننا چاہیں گے؟",

  // ---- Stock detail (extended) ----
  Confidence: "اعتماد",
  "Confidence 5/6 indicators": "اعتماد 5/6 اشارے",
  "RSI (14)": "آر ایس آئی (14)",
  "MA20 vs Price": "MA20 بمقابلہ قیمت",
  "MA50 vs Price": "MA50 بمقابلہ قیمت",
  MACD: "ایم اے سی ڈی",
  "Volume Trend": "حجم کا رجحان",
  "Bollinger Band": "بولنگر بینڈ",
  "Neutral-Bullish": "غیر جانبدار-تیزی",
  "Price > MA20": "قیمت > MA20",
  "Price > MA50": "قیمت > MA50",
  "Bullish cross": "تیزی کا کراس",
  Rising: "بڑھ رہا",
  "Mid-upper": "درمیانی-اوپر",
  "Room to grow": "بڑھنے کی گنجائش",
  "Overall: STRONG BUY · 5 of 6 indicators bullish":
    "مجموعی: اسٹرانگ بائی · 6 میں سے 5 اشارے تیزی میں",
  "is showing strong bullish momentum. Price has broken above MA50 with significantly above-average volume — a classic confirmation signal. RSI at 61 leaves room before overbought territory. The only caution is Bollinger Band position suggesting the move may slow near 148–150. Consider a stop-loss at the MA20 level (~136).":
    "مضبوط تیزی کی رفتار دکھا رہا ہے۔ قیمت نمایاں طور پر اوسط سے زیادہ حجم کے ساتھ MA50 سے اوپر نکل گئی ہے — ایک کلاسک تصدیقی سگنل۔ RSI 61 پر اوور باٹ ہونے سے پہلے گنجائش چھوڑتا ہے۔ واحد احتیاط بولنگر بینڈ کی پوزیشن ہے جو بتاتی ہے کہ حرکت 148–150 کے قریب سست ہو سکتی ہے۔ MA20 سطح (~136) پر اسٹاپ لاس پر غور کریں۔",
  "Banking sector rallies as policy rate held steady":
    "پالیسی ریٹ مستحکم رہنے پر بینکنگ شعبے میں تیزی",
  "Foreign inflows lift PSX to fresh highs":
    "غیر ملکی سرمایہ PSX کو نئی بلندیوں پر لے گیا",
  "Analysts eye resistance near key levels":
    "ماہرین کلیدی سطحوں کے قریب مزاحمت پر نظر رکھے ہوئے",
  Positive: "مثبت",
  "2h ago": "2 گھنٹے پہلے",
  "5h ago": "5 گھنٹے پہلے",
  "1d ago": "1 دن پہلے",

  // ---- Plans (extended) ----
  "Data delay": "ڈیٹا تاخیر",
  Portfolios: "پورٹ فولیوز",
  "AI Advisor queries": "اے آئی ایڈوائزر سوالات",
  Watchlists: "واچ لسٹس",
  "Halal screening": "حلال اسکریننگ",
  "Support tier": "سپورٹ درجہ",
  "15 min delayed": "15 منٹ تاخیر",
  "Real-time": "ریئل ٹائم",
  Unlimited: "لامحدود",
  "3 / month": "3 / ماہ",
  Basic: "بنیادی",
  Priority: "ترجیحی",
  Community: "کمیونٹی",
  Standard: "معیاری",
  "AI-generated · Source grounded": "AI سے تیار کردہ · مستند ذرائع پر مبنی",
  "Private PDF": "نجی پی ڈی ایف",
  "Take Practice Quiz": "مشقی کوئز شروع کریں",
  "Sources used": "استعمال شدہ ذرائع",
  "Key ideas from this lesson": "اس سبق کے اہم نکات",
  "Key terms": "اہم اصطلاحات",
  "Suggested next topics": "اگلے مجوزہ موضوعات",
  "Practice result saved · Official progress unchanged":
    "مشق کا نتیجہ محفوظ ہو گیا · سرکاری پیش رفت میں کوئی تبدیلی نہیں",
  "Educational content only — not financial advice.": "یہ صرف تعلیمی مواد ہے، مالی مشورہ نہیں۔",
};

export function translate(lang: Lang, key: string): string {
  if (lang === "en") return key;
  return UR[key] ?? key;
}

/**
 * App language (English / Urdu) shared across components and persisted.
 * Scoped to the authenticated app — the landing page stays English.
 */
export function useLang() {
  const lang = useSyncExternalStore(
    subscribe,
    () => current,
    () => "en" as Lang,
  );

  const setLang = useCallback((l: Lang) => setStore(l), []);
  const t = useCallback((key: string) => translate(lang, key), [lang]);

  return { lang, setLang, t, isUrdu: lang === "ur" };
}
