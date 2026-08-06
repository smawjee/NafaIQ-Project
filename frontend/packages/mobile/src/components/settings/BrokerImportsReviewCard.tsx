import { useMemo, useState } from "react";
import { Alert, Pressable, StyleSheet, Switch, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { Button, Text } from "@/components/ui";
import { ChipRow, Segmented } from "@/components/ui/controls";
import { radii, type ThemeColors } from "@/constants/theme";
import {
  type BrokerImport,
  useApproveBrokerImport,
  useBrokerAccounts,
  useBrokerImports,
  useRejectBrokerImport,
  useUpdateBrokerAccount,
} from "@/hooks/queries/use-broker-imports";
import { usePortfolioList } from "@/hooks/queries/use-portfolio";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { Check, RefreshCw, Wallet, X } from "@/lib/icons";

function money(value: number | null | undefined): string {
  return value == null ? "—" : `PKR ${Number(value).toLocaleString()}`;
}

export function BrokerImportsReviewCard() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { t } = useLang();
  const { user } = useAuth();
  const imports = useBrokerImports("pending_review", Boolean(user));
  const accounts = useBrokerAccounts(Boolean(user));
  const portfolios = usePortfolioList(Boolean(user));
  const approve = useApproveBrokerImport();
  const reject = useRejectBrokerImport();
  const updateAccount = useUpdateBrokerAccount();
  const [targets, setTargets] = useState<Record<number, number>>({});
  const [autoAfterApproval, setAutoAfterApproval] = useState<Record<number, boolean>>({});

  if (!user || (imports.isLoading && accounts.isLoading)) return null;

  const rows = imports.data?.items ?? [];
  const portfolioRows = portfolios.data ?? [];
  const defaultPortfolioId = portfolioRows[0]?.id;

  const targetFor = (item: BrokerImport) =>
    targets[item.id] ?? item.mapped_portfolio_id ?? defaultPortfolioId;

  const approveImport = async (item: BrokerImport) => {
    const portfolioId = targetFor(item);
    if (!portfolioId) {
      Alert.alert(t("Create a portfolio before approving broker imports."));
      return;
    }
    try {
      await approve.mutateAsync({
        importId: item.id,
        portfolioId,
        enableAuto: Boolean(autoAfterApproval[item.id]),
      });
      Alert.alert(t("Broker confirmation imported"));
    } catch (error) {
      Alert.alert(
        t("Could not approve import"),
        error instanceof Error ? error.message : t("Please try again."),
      );
    }
  };

  const rejectImport = (item: BrokerImport) => {
    Alert.alert(t("Reject broker confirmation?"), item.sanitized_subject, [
      { text: t("Cancel"), style: "cancel" },
      {
        text: t("Reject"),
        style: "destructive",
        onPress: async () => {
          try {
            await reject.mutateAsync(item.id);
          } catch (error) {
            Alert.alert(
              t("Could not reject import"),
              error instanceof Error ? error.message : t("Please try again."),
            );
          }
        },
      },
    ]);
  };

  return (
    <GlassCard style={styles.card}>
      <View style={styles.header}>
        <View style={styles.iconWrap}>
          <Wallet color={colors.primary} size={18} />
        </View>
        <View style={{ flex: 1 }}>
          <Text variant="title" style={{ fontSize: 15 }}>
            {t("Broker imports")}
          </Text>
          <Text variant="muted">
            {rows.length
              ? `${rows.length} ${t("confirmation(s) waiting for review")}`
              : t("No broker confirmations are waiting for review.")}
          </Text>
        </View>
      </View>

      {rows.map((item) => {
        const selectedId = targetFor(item);
        const selectedName = portfolioRows.find((portfolio) => portfolio.id === selectedId)?.name;
        return (
          <View key={item.id} style={styles.importCard}>
            <View style={styles.between}>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ fontWeight: "700" }}>
                  {`${item.broker_code.replaceAll("_", " ")} ${item.account_mask ?? ""}`}
                </Text>
                <Text variant="muted">
                  {`${item.trade_date ?? t("No trade date")} · ${item.item_count ?? item.items?.length ?? 0} ${t("trade(s)")}`}
                </Text>
              </View>
              <Text variant="mono" style={{ fontSize: 12 }}>
                {money(item.total_net_amount)}
              </Text>
            </View>

            {item.items?.length ? (
              <View style={styles.tradeList}>
                {item.items.map((trade) => (
                  <View key={trade.id} style={styles.tradeRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontWeight: "700", fontSize: 12 }}>{trade.symbol}</Text>
                      <Text variant="muted">
                        {`${trade.side.toUpperCase()} · ${trade.quantity.toLocaleString()} @ ${trade.price.toLocaleString()}`}
                      </Text>
                    </View>
                    <View style={{ alignItems: "flex-end" }}>
                      <Text variant="mono" style={{ fontSize: 11 }}>{money(trade.net_amount)}</Text>
                      <Text variant="muted">{`${t("Fees")} ${money(trade.fees)}`}</Text>
                    </View>
                  </View>
                ))}
              </View>
            ) : null}

            {portfolioRows.length ? (
              <View style={{ gap: 5 }}>
                <Text variant="muted">{t("Destination portfolio")}</Text>
                <ChipRow
                  options={portfolioRows.map((portfolio) => portfolio.name)}
                  value={selectedName ?? ""}
                  onChange={(name) => {
                    const portfolio = portfolioRows.find((row) => row.name === name);
                    if (portfolio) {
                      setTargets((current) => ({ ...current, [item.id]: portfolio.id }));
                    }
                  }}
                />
              </View>
            ) : (
              <Text style={{ color: colors.warning }}>{t("No portfolio available")}</Text>
            )}

            <View style={styles.autoRow}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "600", fontSize: 12 }}>{t("Auto-import this broker next time")}</Text>
                <Text variant="muted">{t("Future confirmations use this destination after approval.")}</Text>
              </View>
              <Switch
                value={Boolean(autoAfterApproval[item.id])}
                onValueChange={(value) =>
                  setAutoAfterApproval((current) => ({ ...current, [item.id]: value }))
                }
                trackColor={{ false: colors.border, true: colors.primary + "88" }}
                thumbColor={autoAfterApproval[item.id] ? colors.primary : colors.textMuted}
              />
            </View>

            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <Button
                  title={t("Approve")}
                  onPress={() => approveImport(item)}
                  loading={approve.isPending}
                  disabled={!selectedId}
                  icon={<Check color={colors.primaryForeground} size={15} />}
                />
              </View>
              <Pressable
                onPress={() => rejectImport(item)}
                disabled={reject.isPending}
                style={styles.rejectButton}
                accessibilityRole="button"
                accessibilityLabel={t("Reject")}
              >
                <X color={colors.bear} size={16} />
                <Text style={{ color: colors.bear, fontWeight: "700" }}>{t("Reject")}</Text>
              </Pressable>
            </View>
          </View>
        );
      })}

      {accounts.data?.length ? (
        <View style={styles.accounts}>
          <View style={styles.header}>
            <RefreshCw color={colors.textSecondary} size={15} />
            <Text style={{ fontWeight: "700" }}>{t("Broker account rules")}</Text>
          </View>
          {accounts.data.map((account) => {
            const selectedName = portfolioRows.find(
              (portfolio) => portfolio.id === account.mapped_portfolio_id,
            )?.name;
            return (
              <View key={account.id} style={styles.accountCard}>
                <View style={styles.between}>
                  <Text style={{ fontWeight: "700", flex: 1 }} numberOfLines={1}>
                    {`${account.broker_code.replaceAll("_", " ")} ${account.account_mask}`}
                  </Text>
                  <Text variant="muted">{`${account.pending_count} ${t("pending")}`}</Text>
                </View>
                {portfolioRows.length ? (
                  <ChipRow
                    options={portfolioRows.map((portfolio) => portfolio.name)}
                    value={selectedName ?? ""}
                    onChange={(name) => {
                      const portfolio = portfolioRows.find((row) => row.name === name);
                      if (portfolio) {
                        updateAccount.mutate({
                          accountId: account.id,
                          mapped_portfolio_id: portfolio.id,
                        });
                      }
                    }}
                  />
                ) : null}
                <Segmented
                  options={[t("Review"), t("Auto")]}
                  value={account.mode === "auto" ? t("Auto") : t("Review")}
                  onChange={(value) => {
                    const mode = value === t("Auto") ? "auto" : "review";
                    const mapped = account.mapped_portfolio_id ?? defaultPortfolioId;
                    if (mode === "auto" && !mapped) {
                      Alert.alert(t("Choose a destination portfolio first."));
                      return;
                    }
                    updateAccount.mutate({
                      accountId: account.id,
                      mode,
                      mapped_portfolio_id: mapped,
                    });
                  }}
                />
              </View>
            );
          })}
        </View>
      ) : null}
    </GlassCard>
  );
}

const makeStyles = (colors: ThemeColors) =>
  StyleSheet.create({
    card: { gap: 12, padding: 16 },
    header: { flexDirection: "row", alignItems: "center", gap: 10 },
    iconWrap: {
      width: 38,
      height: 38,
      borderRadius: 13,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.primary + "16",
    },
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10 },
    importCard: {
      gap: 11,
      borderRadius: radii.card,
      borderWidth: 1,
      borderColor: colors.warning + "35",
      backgroundColor: colors.glassFill,
      padding: 13,
    },
    tradeList: { borderRadius: radii.btn, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
    tradeRow: {
      minHeight: 48,
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingHorizontal: 10,
      paddingVertical: 7,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    autoRow: { flexDirection: "row", alignItems: "center", gap: 10 },
    actions: { flexDirection: "row", alignItems: "center", gap: 8 },
    rejectButton: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
      paddingHorizontal: 14,
      borderRadius: radii.btn,
      borderWidth: 1,
      borderColor: colors.bear + "45",
    },
    accounts: { gap: 9, paddingTop: 4 },
    accountCard: {
      gap: 9,
      padding: 12,
      borderRadius: radii.btn,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.glassFill,
    },
  });
