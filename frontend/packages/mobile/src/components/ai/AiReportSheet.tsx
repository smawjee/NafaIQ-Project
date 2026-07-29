/**
 * Reusable AI-report affordance: a glassy trigger pill that opens a liquid-glass
 * bottom sheet rendering an AiReportView, with loading / typed-error / empty
 * states and an optional refresh. The mobile analogue of the web MarketBriefCard
 * + ReportPanel wrappers — used by the dashboard nudge, PSX market brief, stock
 * analysis, and the portfolio/finance report sheets.
 */
import { ReactNode, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import type { ReportContent } from "@nafaiq/shared";

import { AiReportView } from "@/components/ai/AiReportView";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { Text } from "@/components/ui";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { ReportError, reportErrorKey } from "@/lib/ai/reports-client";
import { ChevronRight, RotateCw, Sparkles } from "@/lib/icons";

export function AiReportSheet({
  title,
  subtitle,
  variant = "compact",
  report,
  isLoading,
  error,
  loadingLabel,
  emptyLabel,
  unavailableLabel,
  onOpen,
  onRefresh,
  isRefreshing,
  refreshError,
  trigger,
}: {
  title: string;
  subtitle?: string | null;
  variant?: "compact" | "narrative" | "nudge";
  report?: ReportContent;
  isLoading?: boolean;
  error?: unknown;
  loadingLabel: string;
  emptyLabel: string;
  unavailableLabel?: string;
  onOpen?: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  refreshError?: unknown;
  /** Optional custom trigger; defaults to the glass pill. */
  trigger?: (open: () => void) => ReactNode;
}) {
  const { t } = useLang();
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);

  const show = () => {
    setOpen(true);
    onOpen?.();
  };

  const isUnavailable = error instanceof ReportError && error.code === "unavailable";

  return (
    <>
      {trigger ? (
        trigger(show)
      ) : (
        <Pressable
          onPress={show}
          accessibilityRole="button"
          accessibilityLabel={title}
          style={[styles.pill, { borderColor: colors.border, backgroundColor: colors.aiTint }]}
        >
          <View style={[styles.pillIcon, { backgroundColor: colors.ai + "26" }]}>
            <Sparkles size={18} color={colors.ai} strokeWidth={1.75} />
          </View>
          <View style={{ flex: 1 }}>
            <Text variant="title" style={{ fontSize: 14 }}>
              {title}
            </Text>
            <Text variant="muted" numberOfLines={1} style={{ fontSize: 11, marginTop: 1 }}>
              {isLoading ? loadingLabel : subtitle || emptyLabel}
            </Text>
          </View>
          <ChevronRight size={16} color={colors.textMuted} />
        </Pressable>
      )}

      <GlassSheet open={open} onClose={() => setOpen(false)} title={t("AI Analysis")}>
        <ScrollView style={styles.scroll} contentContainerStyle={{ paddingBottom: 8 }}>
          {isLoading ? (
            <View style={styles.centerRow}>
              <ActivityIndicator color={colors.ai} />
              <Text variant="muted" style={{ fontSize: 12 }}>
                {loadingLabel}
              </Text>
            </View>
          ) : error || !report ? (
            <Text variant="secondary" style={{ fontSize: 13, lineHeight: 20 }}>
              {isUnavailable && unavailableLabel ? unavailableLabel : t(reportErrorKey(error))}
            </Text>
          ) : (
            <AiReportView report={report} variant={variant} />
          )}

          {!!refreshError && (
            <Text variant="muted" style={{ fontSize: 11, marginTop: 8 }}>
              {t(reportErrorKey(refreshError))}
            </Text>
          )}
        </ScrollView>

        {!!onRefresh && (
          <View style={[styles.footer, { borderTopColor: colors.border }]}>
            <Pressable
              onPress={onRefresh}
              disabled={isRefreshing}
              accessibilityRole="button"
              accessibilityLabel={t("Refresh")}
              style={styles.refreshBtn}
              hitSlop={8}
            >
              <RotateCw size={14} color={colors.textMuted} />
              <Text variant="muted" style={{ fontSize: 12 }}>
                {isRefreshing ? t("Refreshing…") : t("Refresh")}
              </Text>
            </Pressable>
          </View>
        )}
      </GlassSheet>
    </>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  pillIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  scroll: { maxHeight: 460 },
  centerRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 20 },
  footer: {
    flexDirection: "row",
    justifyContent: "flex-end",
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 10,
    marginTop: 4,
  },
  refreshBtn: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 8, paddingVertical: 6 },
});
