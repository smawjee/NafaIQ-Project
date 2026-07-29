// Stock detail (`/stock/[ticker]`). Mirrors web `src/features/stock/StockDetail.tsx`:
// header, candlestick chart, stats grid (live fundamentals), technical setup,
// recent announcements, actions. Live data via src/hooks/queries/use-market.ts.
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";

import { Screen } from "@/components/Screen";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { Field } from "@/components/Modal";
import { SignalContextTiles } from "@/components/psx/SignalContextTiles";
import { SignalTrackRecordCard } from "@/components/psx/SignalTrackRecordCard";
import { Button, Card, Change, SignalBadge, Text } from "@/components/ui";
import { Segmented } from "@/components/ui/controls";
import {
  usePsxAnnouncements,
  usePsxCompanyProfile,
  usePsxFundamentals,
  usePsxHistory,
  usePsxQuote,
  usePsxSignalV2,
  usePsxSymbols,
} from "@/hooks/queries/use-market";
import { useWatchlist } from "@/hooks/queries/use-watchlist";
import { useCreatePriceAlert } from "@/hooks/queries/use-price-alerts";
import {
  useAddHolding,
  useCreatePortfolio,
  usePortfolioList,
} from "@/hooks/queries/use-portfolio";
import { useSymbolDividends } from "@/hooks/queries/use-dividends";
import { useAnnualFinancials, useQuarterlyFinancials } from "@/hooks/queries/use-financials";
import { useFilings } from "@/hooks/queries/use-filings";
import { useStockAnalysisReport } from "@/hooks/ai/use-stock-analysis-report";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { ExternalLink, FileText } from "@/lib/icons";
import { fmtNum, type Signal } from "@nafaiq/shared";

/** Compact PKR (mirrors web formatCompactPKR), e.g. 2.15e11 -> "PKR 215B". */
function compactPKR(value: number): string {
  const abs = Math.abs(value);
  const units: [number, string][] = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [threshold, suffix] of units) {
    if (abs >= threshold) {
      const scaled = abs / threshold;
      return `PKR ${scaled.toFixed(scaled < 100 ? 1 : 0)}${suffix}`;
    }
  }
  return `PKR ${fmtNum(value, 0)}`;
}

/** Relative time for announcement rows (mirrors web formatTimeAgo). */
function formatTimeAgo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

export default function StockDetailScreen() {
  const { ticker } = useLocalSearchParams<{ ticker: string }>();
  const { colors } = useTheme();
  const { t } = useLang();
  const { width } = useWindowDimensions();
  const upper = (ticker ?? "HBL").toUpperCase();

  const { data: quote } = usePsxQuote(upper);
  const { data: candles, isPending: candlesPending } = usePsxHistory(upper, 180);
  const { data: profile } = usePsxCompanyProfile(upper);
  const { data: fundamentals } = usePsxFundamentals(upper);
  const { data: announcements, isPending: newsPending } = usePsxAnnouncements(upper, 5);
  const { data: signal } = usePsxSignalV2(upper);
  const { data: symbolsData } = usePsxSymbols();
  const wl = useWatchlist();
  const [wlBusy, setWlBusy] = useState(false);
  // Lazy: only generate the LLM deep-dive when the user opens the sheet.
  const [askedReport, setAskedReport] = useState(false);
  const stockReport = useStockAnalysisReport(upper, askedReport);

  const symbolInfo = symbolsData?.find((x) => x.symbol === upper);

  // Canonical company name: prefer a real name from profile/symbols; never
  // echo the ticker back (avoids "HBL · HBL").
  const rawName = profile?.name || symbolInfo?.name || "";
  const name = rawName && rawName.toUpperCase() !== upper ? rawName : "";
  const sector = profile?.sector ?? symbolInfo?.sector ?? null;

  const price = quote?.price ?? null;
  const changePct = quote?.change_pct ?? null;

  // Signal (v2 engine): the engine declines with "NO SIGNAL" rather than
  // guessing — show no fake call in that case (same rule as web).
  const modelReady = !!signal && signal.signal !== "NO SIGNAL";
  const confidence = signal?.confidence ?? 0;
  const keyDrivers =
    signal?.indicator_votes
      ?.slice(0, 3)
      .map((v) => v.name)
      .join(", ") ?? "";

  const marketCap =
    profile?.listed_shares && price != null ? compactPKR(profile.listed_shares * price) : "—";

  const stats: [string, string][] = [
    ["Market Cap", marketCap],
    ["P/E", fundamentals?.pe != null ? fundamentals.pe.toFixed(1) : "—"],
    ["EPS", fundamentals?.eps != null ? fundamentals.eps.toFixed(2) : "—"],
    ["Day High", quote?.day_high != null ? fmtNum(quote.day_high) : "—"],
    ["Day Low", quote?.day_low != null ? fmtNum(quote.day_low) : "—"],
    ["Volume", quote?.volume != null ? fmtNum(quote.volume, 0) : "—"],
    ["Div Yield", fundamentals?.div_yield != null ? `${fundamentals.div_yield.toFixed(1)}%` : "—"],
    ["P/B", fundamentals?.pb != null ? fundamentals.pb.toFixed(2) : "—"],
  ];

  const isInWatchlist = wl.symbols.includes(upper);

  const toggleWatchlist = async () => {
    if (wlBusy) return;
    setWlBusy(true);
    const wasIn = isInWatchlist;
    try {
      if (wasIn) await wl.remove(upper);
      else await wl.add(upper);
    } catch {
      Alert.alert(t("Watchlist"), t("Something went wrong. Please try again."));
    } finally {
      setWlBusy(false);
    }
  };

  // --- Data tabs (mirror web features/stock StockTabs) ---
  const [tab, setTab] = useState<"Financials" | "Dividends" | "Filings">("Financials");
  const [finPeriod, setFinPeriod] = useState<"Annual" | "Quarterly">("Annual");
  const annualFin = useAnnualFinancials(tab === "Financials" ? upper : undefined, 10);
  const quarterlyFin = useQuarterlyFinancials(tab === "Financials" ? upper : undefined, 20);
  const dividends = useSymbolDividends(tab === "Dividends" ? upper : undefined);
  const filings = useFilings(tab === "Filings" ? upper : undefined, 50);

  // --- Set Price Alert sheet ---
  const createAlert = useCreatePriceAlert();
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertCond, setAlertCond] = useState<"Above" | "Below">("Above");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertErr, setAlertErr] = useState("");

  const openAlert = () => {
    setAlertErr("");
    setAlertCond("Above");
    setAlertPrice(price != null ? String(price) : "");
    setAlertOpen(true);
  };
  const saveAlert = () => {
    setAlertErr("");
    const target = Number(alertPrice);
    if (!alertPrice || Number.isNaN(target) || target <= 0) {
      setAlertErr(t("Please enter a valid target price."));
      return;
    }
    createAlert.mutate(
      {
        symbol: upper,
        condition: alertCond === "Above" ? "above" : "below",
        price: Math.round(target * 100) / 100,
        one_time: false,
        notify_push: true,
        notify_email: false,
      },
      {
        onSuccess: () => {
          setAlertOpen(false);
          Alert.alert(
            t("Price Alert Set"),
            t("You'll be notified when the price crosses your target."),
          );
        },
        onError: () => setAlertErr(t("Could not create the alert. Please try again.")),
      },
    );
  };

  // --- Add to Portfolio sheet ---
  const { data: portfolios } = usePortfolioList();
  const firstPortfolioId = portfolios && portfolios.length > 0 ? portfolios[0].id : null;
  const addHolding = useAddHolding(firstPortfolioId);
  const createPortfolio = useCreatePortfolio();
  const [pfOpen, setPfOpen] = useState(false);
  const [pfShares, setPfShares] = useState("");
  const [pfCost, setPfCost] = useState("");
  const [pfErr, setPfErr] = useState("");
  const pfSaving = addHolding.isPending || createPortfolio.isPending;

  const openPortfolio = () => {
    setPfErr("");
    setPfShares("");
    setPfCost(price != null ? String(price) : "");
    setPfOpen(true);
  };
  const savePortfolio = () => {
    setPfErr("");
    const shares = Number(pfShares);
    const cost = Number(pfCost);
    if (!pfShares || Number.isNaN(shares) || shares <= 0) {
      setPfErr(t("Please enter a valid number of shares."));
      return;
    }
    if (!pfCost || Number.isNaN(cost) || cost <= 0) {
      setPfErr(t("Please enter a valid buy price."));
      return;
    }
    // avg_cost is Numeric(12,2) on the backend — round to stored precision.
    const avg_cost = Math.round(cost * 100) / 100;
    const onError = () => setPfErr(t("Could not add the holding. Please try again."));
    const onSuccess = () => {
      setPfOpen(false);
      Alert.alert(t("Added to Portfolio"), `${upper} ${t("was added to your portfolio.")}`);
    };
    if (firstPortfolioId) {
      addHolding.mutate({ symbol: upper, shares, avg_cost }, { onSuccess, onError });
    } else {
      // First holding ever: auto-create the default portfolio (like web/portfolio.tsx).
      createPortfolio.mutate("Main", {
        onSuccess: (p) =>
          addHolding.mutate({ portfolioId: p.id, symbol: upper, shares, avg_cost }, { onSuccess, onError }),
        onError,
      });
    }
  };

  const subtitle = [name, sector ? t(sector) : null].filter(Boolean).join(" · ");

  return (
    <Screen title={upper} subtitle={subtitle || t("Pakistan Stock Exchange")} back>
      <Card style={{ gap: 8 }}>
        <View style={styles.between}>
          <Text variant="mono" style={{ fontSize: 22 }}>
            {price != null ? fmtNum(price) : "—"}
          </Text>
          {changePct != null && <Change pct={changePct} />}
        </View>
        <View style={styles.between}>
          {modelReady ? (
            <SignalBadge signal={signal!.signal as Signal} />
          ) : (
            <Text variant="muted">{t("Signal unavailable")}</Text>
          )}
          <Text variant="muted">
            {modelReady
              ? `${t("Technical setup")}`
              : t("Technical setup pending")}
          </Text>
        </View>
        {candlesPending ? (
          <View style={styles.chartPlaceholder} accessibilityLabel={t("Loading chart data")}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : candles && candles.length > 0 ? (
          <CandlestickChart data={candles} width={width - 64} height={200} mas={[{ period: 50, color: colors.info }]} />
        ) : (
          <View style={styles.chartPlaceholder}>
            <Text variant="muted">{t("No chart data available.")}</Text>
          </View>
        )}
      </Card>

      <Card style={{ gap: 0 }}>
        <Text variant="title" style={{ marginBottom: 8 }}>
          {t("Key Stats")}
        </Text>
        <View style={styles.statGrid}>
          {stats.map(([k, v]) => (
            <View key={k} style={styles.statCell}>
              <Text variant="muted">{t(k)}</Text>
              <Text variant="mono" style={{ fontSize: 14 }}>
                {v}
              </Text>
            </View>
          ))}
        </View>
      </Card>

      <Card style={{ gap: 8 }}>
        <Text variant="title">{t("NafaIQ Technical Setup")}</Text>
        {modelReady ? (
          <>
            <View style={[styles.verdict, { borderColor: colors.ai + "44" }]}>
              <Text style={{ color: colors.ai, fontWeight: "700" }}>
                {t("Overall")}: {t(signal!.signal)} · {t("Setup strength")} {Math.round(confidence)}%
              </Text>
              <Text variant="secondary">
                {`${upper} — ${t("NafaIQ rates this technical setup")} ${t(signal!.signal)}. ${t("Key drivers")}: ${
                  keyDrivers || t("technical indicators")
                }.`}
              </Text>
            </View>
            {signal!.reasons?.length ? (
              <View style={{ gap: 4 }}>
                {signal!.reasons.slice(0, 3).map((reason) => (
                  <Text key={reason} variant="muted" numberOfLines={2}>
                    · {reason}
                  </Text>
                ))}
              </View>
            ) : null}
            <Text variant="muted" style={{ fontStyle: "italic" }}>
              {t("Technical analysis only. Not financial advice.")}
            </Text>
          </>
        ) : (
          <View style={[styles.pending, { borderColor: colors.border }]}>
            <Text variant="secondary" style={{ fontWeight: "600" }}>
              {t("Signal unavailable — setup pending")}
            </Text>
            <Text variant="muted">
              {t("NafaIQ has not produced a technical setup for this stock yet.")}
            </Text>
          </View>
        )}
        {signal ? <SignalContextTiles signal={signal} /> : null}
      </Card>

      {/* Audited hit rates of published signals — new v2 outcomes store */}
      <SignalTrackRecordCard />

      {/* LLM deep-dive report — verified & cited, separate from the technical setup above */}
      <AiReportSheet
        title={t("AI Stock Analysis")}
        subtitle={stockReport.data?.content?.headline}
        variant="compact"
        report={stockReport.data?.content}
        isLoading={askedReport && stockReport.isLoading}
        error={stockReport.error}
        loadingLabel={t("Generating stock analysis…")}
        emptyLabel={t("Tap for an AI deep-dive on this stock")}
        unavailableLabel={t("This report is being wired to the verified pipeline. The backend is ready.")}
        onOpen={() => setAskedReport(true)}
      />

      <Card style={{ gap: 10 }}>
        <Text variant="title">{t("Recent Announcements")}</Text>
        {newsPending ? (
          <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading announcements")} />
        ) : announcements && announcements.length > 0 ? (
          announcements.map((n) => {
            const inner = (
              <View style={{ gap: 2 }}>
                <Text variant="body" numberOfLines={2}>{n.title}</Text>
                <Text variant="muted">
                  {t(n.category ?? "Corporate")} · {formatTimeAgo(n.posted_at)}
                </Text>
              </View>
            );
            return n.url ? (
              <Pressable
                key={n.id}
                onPress={() => Linking.openURL(n.url!)}
                accessibilityRole="link"
                accessibilityLabel={n.title}
                style={({ pressed }) => [styles.newsRow, pressed && { opacity: 0.7 }]}
              >
                {inner}
              </Pressable>
            ) : (
              <View key={n.id} style={styles.newsRow}>
                {inner}
              </View>
            );
          })
        ) : (
          <Text variant="muted" style={{ paddingVertical: 4 }}>
            {t("No recent announcements.")}
          </Text>
        )}
      </Card>

      {/* Data tabs — Financials / Dividends / Filings (mirror web StockTabs) */}
      <Card style={{ gap: 12 }}>
        <Segmented
          options={["Financials", "Dividends", "Filings"]}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
        />

        {tab === "Financials" ? (
          <View style={{ gap: 10 }}>
            <Segmented
              options={["Annual", "Quarterly"]}
              value={finPeriod}
              onChange={(v) => setFinPeriod(v as typeof finPeriod)}
            />
            {finPeriod === "Annual" ? (
              <TabTable
                head={[t("Year"), t("Sales"), t("EPS"), t("ROE")]}
                loading={annualFin.isPending}
                error={!!annualFin.error}
                empty={t("No annual financials available for this symbol.")}
                rows={(annualFin.data ?? []).map((r) => ({
                  key: String(r.year),
                  cells: [
                    String(r.year),
                    fmtMoney(r.sales),
                    fmtDec(r.eps, 2),
                    fmtDec(r.roe, 1),
                  ],
                }))}
              />
            ) : (
              <TabTable
                head={[t("Period"), t("Sales"), t("Net Income"), t("EPS")]}
                loading={quarterlyFin.isPending}
                error={!!quarterlyFin.error}
                empty={t("No quarterly data available.")}
                rows={(quarterlyFin.data ?? []).map((r) => ({
                  key: r.period,
                  cells: [r.period, fmtMoney(r.sales), fmtMoney(r.net_income), fmtDec(r.eps, 2)],
                }))}
              />
            )}
          </View>
        ) : tab === "Dividends" ? (
          <TabTable
            head={[t("Ex-Date"), t("Type"), t("Per Share"), t("Bonus %")]}
            loading={dividends.isPending}
            error={!!dividends.error}
            empty={t("No dividends data available for this symbol.")}
            rows={(dividends.data ?? []).map((d) => ({
              key: d.announcement_id,
              cells: [
                d.ex_date ?? "—",
                t(d.payout_type),
                fmtDec(d.per_share, 2),
                d.bonus_pct != null ? `${d.bonus_pct}%` : "—",
              ],
            }))}
          />
        ) : (
          <FilingsList
            loading={filings.isPending}
            error={!!filings.error}
            emptyLabel={t("No filings available for this symbol yet.")}
            data={filings.data ?? []}
            iconColor={colors.textMuted}
            linkColor={colors.primary}
            openLabel={t("Open PDF")}
            pagesLabel={t("pages")}
            t={t}
          />
        )}
      </Card>

      <View style={{ gap: 10 }}>
        <Button
          title={isInWatchlist ? t("Remove from Watchlist") : t("Add to Watchlist")}
          loading={wlBusy || wl.loading}
          onPress={toggleWatchlist}
        />
        <Button title={t("Add to Portfolio")} variant="outline" onPress={openPortfolio} />
        <Button title={t("Set Price Alert")} variant="ghost" onPress={openAlert} />
      </View>

      {/* Set Price Alert sheet */}
      <GlassSheet open={alertOpen} onClose={() => setAlertOpen(false)} title={`${t("Set Price Alert")} · ${upper}`}>
        <Text variant="secondary">{t("Condition")}</Text>
        <Segmented
          options={["Above", "Below"]}
          value={alertCond}
          onChange={(v) => setAlertCond(v as typeof alertCond)}
        />
        <Field
          label={t("Target Price (PKR)")}
          value={alertPrice}
          onChangeText={setAlertPrice}
          keyboardType="numeric"
          placeholder="0"
        />
        {alertErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{alertErr}</Text> : null}
        <Button title={t("Create Alert")} onPress={saveAlert} loading={createAlert.isPending} />
      </GlassSheet>

      {/* Add to Portfolio sheet */}
      <GlassSheet open={pfOpen} onClose={() => setPfOpen(false)} title={`${t("Add to Portfolio")} · ${upper}`}>
        <Field label={t("Shares")} value={pfShares} onChangeText={setPfShares} keyboardType="numeric" placeholder="0" />
        <Field label={t("Avg Cost (PKR)")} value={pfCost} onChangeText={setPfCost} keyboardType="numeric" placeholder="0" />
        {pfErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{pfErr}</Text> : null}
        <Button title={t("Add Holding")} onPress={savePortfolio} loading={pfSaving} />
      </GlassSheet>
    </Screen>
  );
}

/** Compact money for financial figures (raw currency rows can be billions). */
function fmtMoney(v: number | null | undefined): string {
  return v == null ? "—" : compactPKR(v);
}

/** Fixed-decimal number, or an em dash when the value is missing. */
function fmtDec(v: number | null | undefined, digits: number): string {
  return v == null ? "—" : v.toFixed(digits);
}

/** Small themed table with loading / empty / error states. Rows are bounded by
 * the backend limit params, so a plain map inside the screen ScrollView is used
 * rather than nesting a VirtualizedList (which React Native warns against). */
function TabTable({
  head,
  rows,
  loading,
  error,
  empty,
}: {
  head: string[];
  rows: { key: string; cells: string[] }[];
  loading: boolean;
  error: boolean;
  empty: string;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  if (loading) return <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading")} />;
  if (error)
    return (
      <Text variant="muted" style={styles.tabState}>
        {t("Something went wrong. Please try again.")}
      </Text>
    );
  if (rows.length === 0)
    return (
      <Text variant="muted" style={styles.tabState}>
        {empty}
      </Text>
    );
  return (
    <View>
      <View style={[styles.tabHead, { borderColor: colors.border }]}>
        {head.map((h, i) => (
          <Text key={h} variant="muted" style={i === 0 ? styles.cell : styles.cellRight} numberOfLines={1}>
            {h}
          </Text>
        ))}
      </View>
      {rows.map((r) => (
        <View key={r.key} style={[styles.tabRow, { borderColor: colors.border }]}>
          {r.cells.map((c, i) => (
            <Text key={i} variant="mono" style={[i === 0 ? styles.cell : styles.cellRight, { fontSize: 13 }]} numberOfLines={1}>
              {c}
            </Text>
          ))}
        </View>
      ))}
    </View>
  );
}

/** Per-symbol filings list. Rows deep-link to the original PDF (the list
 * endpoint omits the extracted body, so there is nothing to expand inline). */
function FilingsList({
  data,
  loading,
  error,
  emptyLabel,
  iconColor,
  linkColor,
  openLabel,
  pagesLabel,
  t,
}: {
  data: { announcement_id: string; type: string | null; filed_at: string | null; pdf_url: string | null; page_count: number | null }[];
  loading: boolean;
  error: boolean;
  emptyLabel: string;
  iconColor: string;
  linkColor: string;
  openLabel: string;
  pagesLabel: string;
  t: (k: string) => string;
}) {
  if (loading) return <ActivityIndicator color={linkColor} accessibilityLabel={t("Loading filings")} />;
  if (error)
    return (
      <Text variant="muted" style={styles.tabState}>
        {t("Something went wrong. Please try again.")}
      </Text>
    );
  if (data.length === 0)
    return (
      <Text variant="muted" style={styles.tabState}>
        {emptyLabel}
      </Text>
    );
  return (
    <View style={{ gap: 8 }}>
      {data.map((f) => {
        const title = `${t(f.type ?? "Filing")}`;
        const meta = [
          f.filed_at ? formatTimeAgo(f.filed_at) : null,
          f.page_count != null ? `${f.page_count} ${pagesLabel}` : null,
        ]
          .filter(Boolean)
          .join(" · ");
        const inner = (
          <>
            <FileText color={iconColor} size={16} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text variant="body" numberOfLines={2}>
                {title}
              </Text>
              <Text variant="muted">{meta || "—"}</Text>
            </View>
            {f.pdf_url ? <ExternalLink color={linkColor} size={16} /> : null}
          </>
        );
        return f.pdf_url ? (
          <Pressable
            key={f.announcement_id}
            onPress={() => Linking.openURL(f.pdf_url!)}
            accessibilityRole="link"
            accessibilityLabel={`${title}. ${openLabel}`}
            style={({ pressed }) => [styles.filingRow, pressed && { opacity: 0.7 }]}
          >
            {inner}
          </Pressable>
        ) : (
          <View key={f.announcement_id} style={styles.filingRow}>
            {inner}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statGrid: { flexDirection: "row", flexWrap: "wrap" },
  statCell: { width: "25%", paddingVertical: 6, gap: 2 },
  chartPlaceholder: { height: 200, alignItems: "center", justifyContent: "center" },
  verdict: { borderWidth: 1, borderRadius: 10, padding: 10, gap: 4, marginTop: 4 },
  pending: { borderWidth: 1, borderStyle: "dashed", borderRadius: 10, padding: 12, gap: 4, alignItems: "center" },
  newsRow: { gap: 2, minHeight: 44, justifyContent: "center" },
  tabState: { paddingVertical: 16, textAlign: "center" },
  tabHead: { flexDirection: "row", borderBottomWidth: 1, paddingBottom: 6, marginBottom: 2 },
  tabRow: { flexDirection: "row", alignItems: "center", minHeight: 40, paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth },
  cell: { flex: 1.1 },
  cellRight: { flex: 1, textAlign: "right" },
  filingRow: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44, paddingVertical: 4 },
});
