/**
 * Renders a generated AI report body — shared by the dashboard nudge, the PSX
 * market brief, the stock analysis card, and the portfolio/finance report
 * sheets. Ported from web components/ai/AiReportView.tsx.
 *
 * Content arrives already localized from the backend (?lang), so only section
 * chrome runs through t(). `variant` controls density:
 *   - "compact"   (default): bulleted observations, full report
 *   - "narrative":           paragraph observations, full report
 *   - "nudge":               paragraphs, considerations + disclaimer only
 *                            (no citations / deep sections) — dashboard nudge
 */
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import type {
  ReportContent,
  ReportMetric,
  ReportSection,
} from "@nafaiq/shared";

import { Text } from "@/components/ui";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { ChevronDown, ChevronRight } from "@/lib/icons";

type Variant = "compact" | "narrative" | "nudge";

export function AiReportView({
  report,
  variant = "compact",
}: {
  report: ReportContent;
  variant?: Variant;
}) {
  const { t, isUrdu } = useLang();
  const { colors } = useTheme();
  const showDeep = variant !== "nudge";
  const sections = useMemo(() => getDetailedSections(report), [report]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const rtl = isUrdu ? ({ writingDirection: "rtl", textAlign: "right" } as const) : undefined;

  const Bulleted = ({ items }: { items: string[] }) => (
    <View style={{ gap: 8 }}>
      {items.map((o, i) => (
        <View key={i} style={styles.bulletRow}>
          <View style={[styles.dot, { backgroundColor: colors.ai }]} />
          <Text variant="secondary" style={[styles.body, rtl, { flex: 1 }]}>
            {o}
          </Text>
        </View>
      ))}
    </View>
  );

  return (
    <View style={{ gap: 16 }}>
      {!!report.headline && (
        <Text variant="title" style={[{ fontSize: 15, lineHeight: 22 }, rtl]}>
          {report.headline}
        </Text>
      )}

      {report.observations?.length > 0 &&
        (variant === "compact" ? (
          <Bulleted items={report.observations} />
        ) : (
          <View style={{ gap: 8 }}>
            {report.observations.map((o, i) => (
              <Text key={i} variant="secondary" style={[styles.body, rtl]}>
                {o}
              </Text>
            ))}
          </View>
        ))}

      {showDeep && !!report.executive_summary && (
        <Section title={t("Executive summary")} colors={colors}>
          <Text variant="secondary" style={[styles.body, rtl]}>
            {report.executive_summary}
          </Text>
        </Section>
      )}

      {showDeep &&
        sections.map((section) => (
          <Section key={section.title} title={section.title} colors={colors}>
            <Text variant="secondary" style={[styles.body, rtl]}>
              {section.summary}
            </Text>
            {!!section.supporting_metrics?.length && (
              <View style={styles.metricGrid}>
                {section.supporting_metrics.map((m) => (
                  <MetricPill key={`${m.label}-${m.source_key}`} metric={m} colors={colors} />
                ))}
              </View>
            )}
            {!!section.key_findings?.length && (
              <View style={{ gap: 6, marginTop: 4 }}>
                {section.key_findings.map((f, i) => (
                  <View key={i} style={styles.bulletRow}>
                    <View style={[styles.dot, { backgroundColor: colors.ai }]} />
                    <Text variant="secondary" style={[styles.body, rtl, { flex: 1 }]}>
                      {f}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </Section>
        ))}

      {showDeep && !!report.holdings_analysis?.length && (
        <Section title={t("Holdings review")} colors={colors}>
          <View style={{ gap: 10 }}>
            {report.holdings_analysis.map((h) => (
              <View key={h.symbol} style={[styles.leftRule, { borderLeftColor: colors.ai }]}>
                <Text variant="title" style={{ fontSize: 13 }}>
                  {h.symbol}
                </Text>
                <Text variant="secondary" style={[styles.body, rtl]}>
                  {h.summary}
                </Text>
                {!!h.risk_note && (
                  <Text variant="muted" style={[styles.small, rtl]}>
                    {h.risk_note}
                  </Text>
                )}
              </View>
            ))}
          </View>
        </Section>
      )}

      {showDeep && !!report.action_plan?.length && (
        <Section title={t("Action plan")} colors={colors}>
          <View style={{ gap: 10 }}>
            {report.action_plan.map((item, i) => (
              <View key={`${item.title}-${i}`} style={[styles.leftRule, { borderLeftColor: colors.ai }]}>
                <View style={styles.tagRow}>
                  <Text variant="title" style={{ fontSize: 13 }}>
                    {item.title}
                  </Text>
                  <Tag label={t(item.priority)} colors={colors} />
                  <Tag label={t(item.timeframe.replace(/_/g, " "))} colors={colors} />
                </View>
                <Text variant="secondary" style={[styles.body, rtl]}>
                  {item.rationale}
                </Text>
              </View>
            ))}
          </View>
        </Section>
      )}

      {showDeep && report.ml_signal_status === "not_available" && !!report.ml_signal_note && (
        <Text variant="muted" style={[styles.small, rtl, styles.topRule, { borderTopColor: colors.border }]}>
          {report.ml_signal_note}
        </Text>
      )}

      {showDeep && !!report.data_quality_notes?.length && (
        <Section title={t("Data quality")} colors={colors}>
          {report.data_quality_notes.map((note, i) => (
            <Text key={i} variant="muted" style={[styles.small, rtl]}>
              {note}
            </Text>
          ))}
        </Section>
      )}

      {report.considerations?.length > 0 && (
        <View style={{ gap: 8 }}>
          <Text variant="muted" style={styles.sectionLabel}>
            {t("Things to consider")}
          </Text>
          {report.considerations.map((c, i) => (
            <View
              key={i}
              style={[
                styles.considerCard,
                { borderColor: colors.border, borderLeftColor: colors.ai, backgroundColor: colors.aiTint },
              ]}
            >
              <Text style={[styles.body, rtl, { color: colors.textPrimary }]}>{c.consideration}</Text>
              <Text variant="secondary" style={[styles.small, rtl, { fontStyle: "italic", marginTop: 4 }]}>
                {c.hedge}
              </Text>
            </View>
          ))}
        </View>
      )}

      {!!report.disclaimer && (
        <Text
          variant="muted"
          style={[
            styles.small,
            rtl,
            { fontStyle: "italic" },
            showDeep && [styles.topRule, { borderTopColor: colors.border }],
          ]}
        >
          {report.disclaimer}
        </Text>
      )}

      {showDeep && !!report.citations?.length && (
        <View>
          <Pressable
            onPress={() => setSourcesOpen((v) => !v)}
            accessibilityRole="button"
            accessibilityLabel={t("View sources")}
            style={styles.sourcesToggle}
            hitSlop={8}
          >
            {sourcesOpen ? (
              <ChevronDown size={14} color={colors.textMuted} />
            ) : (
              <ChevronRight size={14} color={colors.textMuted} />
            )}
            <Text variant="muted" style={styles.small}>
              {t("View sources")}
            </Text>
          </Pressable>
          {sourcesOpen && (
            <View style={{ gap: 4, marginTop: 6 }}>
              {report.citations.map((c, i) => (
                <Text key={i} variant="muted" style={styles.small}>
                  <Text variant="secondary" style={styles.small}>
                    {String(c.value)}
                  </Text>
                  {` — from ${c.source_key} (as_of: ${c.as_of})`}
                </Text>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
}

function Section({
  title,
  colors,
  children,
}: {
  title: string;
  colors: ReturnType<typeof useTheme>["colors"];
  children: React.ReactNode;
}) {
  return (
    <View style={[styles.section, styles.topRule, { borderTopColor: colors.border }]}>
      <Text variant="muted" style={styles.sectionLabel}>
        {title}
      </Text>
      {children}
    </View>
  );
}

function Tag({ label, colors }: { label: string; colors: ReturnType<typeof useTheme>["colors"] }) {
  return (
    <View style={[styles.tag, { borderColor: colors.border }]}>
      <Text variant="muted" style={{ fontSize: 10 }}>
        {label}
      </Text>
    </View>
  );
}

function MetricPill({
  metric,
  colors,
}: {
  metric: ReportMetric;
  colors: ReturnType<typeof useTheme>["colors"];
}) {
  return (
    <View style={[styles.metricPill, { borderColor: colors.border, backgroundColor: colors.surface }]}>
      <Text variant="muted" style={{ fontSize: 10, textTransform: "uppercase" }}>
        {metric.label}
      </Text>
      <Text variant="mono" style={{ fontSize: 13, marginTop: 2 }}>
        {formatMetricValue(metric.value)}
      </Text>
      {!!metric.interpretation && (
        <Text variant="secondary" style={[styles.small, { marginTop: 2 }]}>
          {metric.interpretation}
        </Text>
      )}
    </View>
  );
}

function getDetailedSections(report: ReportContent): ReportSection[] {
  if (report.report_type === "finance") {
    return [
      withTitle(report.financial_health, "Financial health"),
      withTitle(report.income_analysis, "Income analysis"),
      withTitle(report.expense_analysis, "Expense analysis"),
      withTitle(report.cashflow_analysis, "Cash flow analysis"),
      withTitle(report.savings_analysis, "Savings analysis"),
      withTitle(report.budget_analysis, "Budget analysis"),
      withTitle(report.goal_progress, "Goal progress"),
      withTitle(report.emergency_fund_review, "Emergency fund review"),
    ].filter(Boolean) as ReportSection[];
  }
  if (report.report_type === "portfolio") {
    return [
      withTitle(report.portfolio_health, "Portfolio health"),
      withTitle(report.profit_loss_analysis, "Profit/loss analysis"),
      withTitle(report.allocation_analysis, "Allocation analysis"),
      withTitle(report.risk_analysis, "Risk analysis"),
    ].filter(Boolean) as ReportSection[];
  }
  return [];
}

function withTitle(section: ReportSection | null | undefined, fallback: string) {
  if (!section) return section;
  return { ...section, title: section.title || fallback };
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number" || typeof value === "string") return String(value);
  if (Array.isArray(value)) return `${value.length} items`;
  if (value && typeof value === "object") return "Details available";
  return "--";
}

const styles = StyleSheet.create({
  body: { fontSize: 13, lineHeight: 20 },
  small: { fontSize: 11, lineHeight: 16 },
  bulletRow: { flexDirection: "row", gap: 8, alignItems: "flex-start" },
  dot: { width: 6, height: 6, borderRadius: 3, marginTop: 7 },
  section: { gap: 8, paddingTop: 14 },
  sectionLabel: { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 },
  topRule: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 12 },
  leftRule: { borderLeftWidth: 2, paddingLeft: 10, gap: 2 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6 },
  tag: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  metricPill: { flexGrow: 1, minWidth: "45%", borderWidth: StyleSheet.hairlineWidth, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 8 },
  considerCard: { borderWidth: StyleSheet.hairlineWidth, borderLeftWidth: 4, borderRadius: 10, padding: 12 },
  sourcesToggle: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
});
