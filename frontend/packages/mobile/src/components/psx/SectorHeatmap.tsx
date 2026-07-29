// Sector Heatmap — mobile port of the web app's PsxSectorHeatmap
// (frontend/packages/web/src/features/psx/components/PsxSectorHeatmap.tsx).
//
// Zoomed-out default: a squarified treemap of every sector (one tile per
// sector, sized by the active metric, coloured by avg % change). Tapping a
// sector drills into a full-screen treemap of that sector's stocks. A List
// view swaps the mosaic for a sector bar-list plus a Top Movers table (movers
// only appear in list view, per product spec). The size/volume/%-change filter
// drives tile sizing + ordering at both levels. Liquid-glass surfaces + the
// app's bull/bear ramp keep it consistent with the rest of PSX.
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal as RNModal,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Text } from "@/components/ui";
import { type ThemeColors } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import type { ApiTreemap, ApiTreemapSector, ApiTreemapStock } from "@/hooks/queries/use-market";
import { ArrowLeft, Flame, LayoutGrid, List, TrendingDown, TrendingUp, X } from "@/lib/icons";
import { squarify, type TreemapTile } from "@/lib/treemap";

type Metric = "size" | "volume" | "change";
const METRICS: { key: Metric; label: string }[] = [
  { key: "size", label: "By Size" },
  { key: "volume", label: "By Volume" },
  { key: "change", label: "By % Change" },
];

const GRID_HEIGHT = 340;
const CARD_PAD = 14; // GlassCard inner padding on each side

/* ── metric accessors ── */
function sectorValue(s: ApiTreemapSector, m: Metric): number {
  if (m === "volume") return s.stocks.reduce((n, st) => n + Math.max(st.volume, 0), 0);
  if (m === "change") return Math.max(Math.abs(s.avg_change_pct), 0.05);
  return Math.max(s.total_size_metric, 0);
}
function stockValue(st: ApiTreemapStock, m: Metric): number {
  if (m === "volume") return Math.max(st.volume, 0);
  if (m === "change") return Math.max(Math.abs(st.change_pct), 0.05);
  return Math.max(st.size_metric, 0);
}

/* ── colour ramp (elevated → bull/bear by |change|) ── */
function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const v = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}
function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * t);
}
function tileColor(pct: number, c: ThemeColors): string {
  const base = hexToRgb(c.elevated);
  if (Math.abs(pct) <= 0.1) return `rgb(${base[0]},${base[1]},${base[2]})`;
  const target = hexToRgb(pct >= 0 ? c.bull : c.bear);
  const t = 0.18 + Math.min(Math.abs(pct) / 3, 1) * 0.62; // 0.18 → 0.80
  return `rgb(${lerp(base[0], target[0], t)},${lerp(base[1], target[1], t)},${lerp(base[2], target[2], t)})`;
}

function fmtCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${Math.round(n)}`;
}
function sectorAbbr(name: string): string {
  return name.split(/\s+/).filter(Boolean).map((p) => p[0]).join("").slice(0, 4).toUpperCase();
}
function pctLabel(pct: number): string {
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/* ══ tile ══ */
function HeatTile({
  x, y, w, h, color, label, sub, onPress, a11y,
}: {
  x: number; y: number; w: number; h: number;
  color: string; label: string; sub: string;
  onPress: () => void; a11y: string;
}) {
  const showLabel = w >= 40 && h >= 26;
  const showSub = h >= 42 && w >= 44;
  const gap = 1.5;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={a11y}
      style={{
        position: "absolute",
        left: x + gap,
        top: y + gap,
        width: Math.max(0, w - gap * 2),
        height: Math.max(0, h - gap * 2),
        backgroundColor: color,
        borderRadius: 4,
        paddingHorizontal: 4,
        paddingVertical: 3,
        overflow: "hidden",
        justifyContent: "flex-start",
      }}
    >
      {showLabel && (
        <Text numberOfLines={1} style={styles.tileLabel}>
          {label}
        </Text>
      )}
      {showSub && (
        <Text numberOfLines={1} style={styles.tileSub}>
          {sub}
        </Text>
      )}
    </Pressable>
  );
}

/* ══ segmented pill (metric filter) ══ */
function Filter({ metric, onChange, t }: { metric: Metric; onChange: (m: Metric) => void; t: (s: string) => string }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.filterWrap, { backgroundColor: colors.glassFill, borderColor: colors.border }]}>
      {METRICS.map((m) => {
        const active = m.key === metric;
        return (
          <Pressable
            key={m.key}
            onPress={() => onChange(m.key)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            style={[styles.filterItem, active && { backgroundColor: colors.glassFill }]}
          >
            <Text numberOfLines={1} style={{ fontSize: 11, fontWeight: active ? "700" : "500", color: active ? colors.textPrimary : colors.textMuted }}>
              {t(m.label)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/* ══ grid/list view toggle ══ */
function ViewToggle({ view, onChange, t }: { view: "grid" | "list"; onChange: (v: "grid" | "list") => void; t: (s: string) => string }) {
  const { colors } = useTheme();
  const Btn = ({ v, Icon, label }: { v: "grid" | "list"; Icon: typeof LayoutGrid; label: string }) => {
    const active = v === view;
    return (
      <Pressable
        onPress={() => onChange(v)}
        accessibilityRole="button"
        accessibilityLabel={t(label)}
        accessibilityState={{ selected: active }}
        style={[styles.toggleBtn, active ? { backgroundColor: colors.bull } : null]}
      >
        <Icon color={active ? "#04150f" : colors.textMuted} size={15} />
      </Pressable>
    );
  };
  return (
    <View style={[styles.toggleWrap, { backgroundColor: colors.glassFill, borderColor: colors.border }]}>
      <Btn v="grid" Icon={LayoutGrid} label="Heatmap view" />
      <Btn v="list" Icon={List} label="List view" />
    </View>
  );
}

function Legend({ colors, t }: { colors: ThemeColors; t: (s: string) => string }) {
  const swatch = (pct: number) => ({ backgroundColor: tileColor(pct, colors) });
  return (
    <View style={styles.legend}>
      <Text variant="muted" style={{ fontSize: 10 }}>{t("Loss")}</Text>
      {[-2.4, -1, 0, 1, 2.4].map((p) => (
        <View key={p} style={[styles.legendSwatch, swatch(p)]} />
      ))}
      <Text variant="muted" style={{ fontSize: 10 }}>{t("Gain")}</Text>
    </View>
  );
}

/* ══════════════════════ main ══════════════════════ */
export function SectorHeatmap({
  data,
  isPending,
  isError,
  onStockPress,
}: {
  data?: ApiTreemap;
  isPending: boolean;
  isError: boolean;
  onStockPress: (symbol: string) => void;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  const { width } = useWindowDimensions();
  const [metric, setMetric] = useState<Metric>("size");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [drilled, setDrilled] = useState<string | null>(null);

  const gridWidth = width - 32 - CARD_PAD * 2; // screen pad + card pad

  const sectors = useMemo(() => data?.sectors ?? [], [data]);

  // Sector tiles for the zoomed-out mosaic, largest-first for a square layout.
  const sectorTiles = useMemo<TreemapTile<ApiTreemapSector>[]>(() => {
    const items = sectors
      .map((s) => ({ value: sectorValue(s, metric), data: s }))
      .sort((a, b) => b.value - a.value);
    return squarify(items, gridWidth, GRID_HEIGHT);
  }, [sectors, metric, gridWidth]);

  // Sector rows for the list view, ordered by the active metric.
  const sortedSectors = useMemo(
    () => [...sectors].sort((a, b) => sectorValue(b, metric) - sectorValue(a, metric)),
    [sectors, metric],
  );

  // Top movers (list view only) — biggest absolute % movers across all tiles.
  const topMovers = useMemo(() => {
    return sectors
      .flatMap((s) => s.stocks.map((st) => ({ ...st, sector: st.sector ?? s.name })))
      .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
      .slice(0, 12);
  }, [sectors]);

  const drilledSector = useMemo(
    () => (drilled ? sectors.find((s) => s.name === drilled) ?? null : null),
    [drilled, sectors],
  );

  const totalStocks = sectors.reduce((n, s) => n + s.stock_count, 0);

  if (isPending) {
    return (
      <GlassCard style={styles.card}>
        <View style={styles.empty}>
          <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading sector heatmap")} />
        </View>
      </GlassCard>
    );
  }
  if (isError || sectors.length === 0) {
    return (
      <GlassCard style={styles.card}>
        <View style={styles.empty}>
          <Text variant="muted">{isError ? t("Could not load heatmap.") : t("No sector data available.")}</Text>
        </View>
      </GlassCard>
    );
  }

  return (
    <>
      <GlassCard style={styles.card}>
        {/* header */}
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text variant="title" style={{ fontSize: 16 }}>{t("Sector Heatmap")}</Text>
            <Text variant="muted" style={{ fontSize: 11, marginTop: 1 }}>
              {sectors.length} {t("sectors")} · {totalStocks} {t("stocks")}
            </Text>
          </View>
          <ViewToggle view={view} onChange={setView} t={t} />
        </View>

        <View style={styles.controlsRow}>
          <Filter metric={metric} onChange={setMetric} t={t} />
        </View>
        <Legend colors={colors} t={t} />

        {view === "grid" ? (
          <View style={{ width: gridWidth, height: GRID_HEIGHT, marginTop: 10, alignSelf: "center" }}>
            {sectorTiles.map((tile) => {
              const s = tile.data;
              return (
                <HeatTile
                  key={s.name}
                  x={tile.x}
                  y={tile.y}
                  w={tile.w}
                  h={tile.h}
                  color={tileColor(s.avg_change_pct, colors)}
                  label={tile.w < 66 ? sectorAbbr(t(s.name)) : t(s.name)}
                  sub={pctLabel(s.avg_change_pct)}
                  onPress={() => setDrilled(s.name)}
                  a11y={`${t(s.name)}, ${s.stock_count} ${t("stocks")}, ${pctLabel(s.avg_change_pct)}. ${t("Tap to view stocks")}`}
                />
              );
            })}
          </View>
        ) : (
          <View style={{ marginTop: 10, gap: 18 }}>
            {/* Top movers — list view only */}
            <View style={{ gap: 6 }}>
              <View style={styles.sectionHead}>
                <Flame color={colors.gold} size={14} />
                <Text style={{ fontSize: 13, fontWeight: "700", color: colors.textPrimary }}>{t("Top Movers")}</Text>
              </View>
              <View style={[styles.moversTable, { borderColor: colors.border }]}>
                {topMovers.map((m, i) => {
                  const up = m.change_pct >= 0;
                  return (
                    <Pressable
                      key={m.symbol}
                      onPress={() => onStockPress(m.symbol)}
                      accessibilityRole="button"
                      accessibilityLabel={`${m.symbol}, ${pctLabel(m.change_pct)}`}
                      style={[styles.moverRow, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border }]}
                    >
                      <Text variant="muted" style={{ width: 20, fontSize: 12 }}>{i + 1}</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 13, fontWeight: "700", color: colors.textPrimary }}>{m.symbol}</Text>
                        <Text variant="muted" style={{ fontSize: 10.5 }} numberOfLines={1}>{t(m.sector ?? "—")}</Text>
                      </View>
                      <Text variant="mono" style={{ fontSize: 12, color: colors.textSecondary, width: 62, textAlign: "right" }}>
                        {fmtCompact(m.volume)}
                      </Text>
                      <View style={styles.moverChange}>
                        {up ? <TrendingUp color={colors.bull} size={13} /> : <TrendingDown color={colors.bear} size={13} />}
                        <Text variant="mono" style={{ fontSize: 12.5, fontWeight: "700", color: up ? colors.bull : colors.bear }}>
                          {Math.abs(m.change_pct).toFixed(2)}%
                        </Text>
                      </View>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            {/* Sector bar list */}
            <View style={{ gap: 6 }}>
              <Text style={{ fontSize: 13, fontWeight: "700", color: colors.textPrimary }}>{t("Sectors")}</Text>
              <View style={{ gap: 3 }}>
                {sortedSectors.map((s) => {
                  const up = s.avg_change_pct >= 0;
                  return (
                    <Pressable
                      key={s.name}
                      onPress={() => setDrilled(s.name)}
                      accessibilityRole="button"
                      accessibilityLabel={`${t(s.name)}, ${s.stock_count} ${t("stocks")}, ${pctLabel(s.avg_change_pct)}. ${t("Tap to view stocks")}`}
                      style={styles.sectorRow}
                    >
                      <Text style={{ width: 96, fontSize: 12, fontWeight: "600", color: colors.textPrimary }} numberOfLines={1}>
                        {t(s.name)}
                      </Text>
                      <Text variant="muted" style={{ fontSize: 11, width: 22 }}>{s.stock_count}</Text>
                      <View style={[styles.barTrack, { backgroundColor: colors.glassFill }]}>
                        <View
                          style={{
                            height: "100%",
                            borderRadius: 3,
                            width: `${Math.min(Math.abs(s.avg_change_pct) * 12, 100)}%`,
                            backgroundColor: up ? colors.bull : colors.bear,
                          }}
                        />
                      </View>
                      <Text variant="mono" style={{ fontSize: 12, fontWeight: "700", width: 58, textAlign: "right", color: up ? colors.bull : colors.bear }}>
                        {pctLabel(s.avg_change_pct)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          </View>
        )}
      </GlassCard>

      {/* ══ drill: full-screen sector treemap ══ */}
      <DrillModal
        sector={drilledSector}
        metric={metric}
        onMetric={setMetric}
        onClose={() => setDrilled(null)}
        onStockPress={(sym) => {
          setDrilled(null);
          onStockPress(sym);
        }}
      />
    </>
  );
}

/* ══ full-screen drill modal ══ */
function DrillModal({
  sector, metric, onMetric, onClose, onStockPress,
}: {
  sector: ApiTreemapSector | null;
  metric: Metric;
  onMetric: (m: Metric) => void;
  onClose: () => void;
  onStockPress: (symbol: string) => void;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  const [box, setBox] = useState({ w: 0, h: 0 });

  const tiles = useMemo<TreemapTile<ApiTreemapStock>[]>(() => {
    if (!sector || box.w <= 0 || box.h <= 0) return [];
    const items = sector.stocks
      .map((st) => ({ value: stockValue(st, metric), data: st }))
      .sort((a, b) => b.value - a.value);
    return squarify(items, box.w, box.h);
  }, [sector, metric, box]);

  const up = (sector?.avg_change_pct ?? 0) >= 0;

  return (
    <RNModal
      visible={!!sector}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <GlassScreen>
        <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right", "bottom"]}>
          <View style={[styles.drillHeader, { borderBottomColor: colors.border }]}>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel={t("Back to all sectors")} style={styles.drillBack}>
              <ArrowLeft color={colors.textPrimary} size={22} />
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text variant="title" style={{ fontSize: 17 }} numberOfLines={1}>{sector ? t(sector.name) : ""}</Text>
              {sector && (
                <Text variant="muted" style={{ fontSize: 11.5, marginTop: 1 }}>
                  {sector.stock_count} {t("stocks")} ·{" "}
                  <Text variant="mono" style={{ fontSize: 11.5, color: up ? colors.bull : colors.bear }}>
                    {pctLabel(sector.avg_change_pct)}
                  </Text>
                </Text>
              )}
            </View>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel={t("Close")}>
              <X color={colors.textMuted} size={22} />
            </Pressable>
          </View>

          <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
            <Filter metric={metric} onChange={onMetric} t={t} />
          </View>

          <View
            style={{ flex: 1, margin: 16, marginTop: 12 }}
            onLayout={(e) => setBox({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}
          >
            {tiles.map((tile) => {
              const st = tile.data;
              return (
                <HeatTile
                  key={st.symbol}
                  x={tile.x}
                  y={tile.y}
                  w={tile.w}
                  h={tile.h}
                  color={tileColor(st.change_pct, colors)}
                  label={st.symbol}
                  sub={pctLabel(st.change_pct)}
                  onPress={() => onStockPress(st.symbol)}
                  a11y={`${st.symbol}, ${st.name}, ${pctLabel(st.change_pct)}. ${t("Open stock")}`}
                />
              );
            })}
          </View>
        </SafeAreaView>
      </GlassScreen>
    </RNModal>
  );
}

const styles = StyleSheet.create({
  card: { padding: CARD_PAD },
  empty: { paddingVertical: 40, alignItems: "center", justifyContent: "center" },
  headerRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  controlsRow: { marginTop: 12 },
  filterWrap: { flexDirection: "row", borderWidth: 1, borderRadius: 9, padding: 2, gap: 2 },
  filterItem: { flex: 1, alignItems: "center", justifyContent: "center", paddingVertical: 7, borderRadius: 7 },
  toggleWrap: { flexDirection: "row", borderWidth: 1, borderRadius: 9, padding: 2, gap: 2 },
  toggleBtn: { width: 34, height: 30, alignItems: "center", justifyContent: "center", borderRadius: 7 },
  legend: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 10 },
  legendSwatch: { width: 22, height: 8, borderRadius: 2 },
  tileLabel: { fontSize: 10.5, fontWeight: "800", color: "#fff", textShadowColor: "rgba(0,0,0,0.35)", textShadowOffset: { width: 0, height: 1 }, textShadowRadius: 2 },
  tileSub: { fontSize: 9.5, fontWeight: "600", color: "rgba(255,255,255,0.92)", marginTop: 1, textShadowColor: "rgba(0,0,0,0.35)", textShadowOffset: { width: 0, height: 1 }, textShadowRadius: 2 },
  sectionHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  moversTable: { borderWidth: 1, borderRadius: 10, overflow: "hidden" },
  moverRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 10, paddingVertical: 8, minHeight: 46 },
  moverChange: { flexDirection: "row", alignItems: "center", gap: 3, width: 70, justifyContent: "flex-end" },
  sectorRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 7, minHeight: 44 },
  barTrack: { flex: 1, height: 7, borderRadius: 3, overflow: "hidden" },
  drillHeader: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 16, paddingTop: 6, paddingBottom: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  drillBack: { minWidth: 40, minHeight: 40, alignItems: "center", justifyContent: "center", marginLeft: -8 },
});
