// Market News (`/news`): virtualized feed of the latest PSX headlines from
// GET /api/news/latest via useLatestNews(). Tapping a story opens its source
// URL in the browser (Linking.openURL). Mirrors web features/psx NewsFeed.
import { Stack, useRouter } from "expo-router";
import { useCallback, useMemo } from "react";
import { ActivityIndicator, FlatList, Linking, Platform, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Card, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { type NewsItem, useLatestNews } from "@/hooks/queries/use-news";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft, ExternalLink } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

/** Compact relative time — "5m", "3h", "2d", else a short date. */
function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const diff = Date.now() - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).href;
  } catch {
    return null;
  }
}

export default function NewsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const { data, isPending, isError, refetch } = useLatestNews(30);
  const items = data ?? [];

  const openStory = useCallback((url: string | null | undefined) => {
    const href = safeUrl(url);
    if (href) Linking.openURL(href).catch(() => undefined);
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: NewsItem }) => {
      const href = safeUrl(item.url);
      const meta = [timeAgo(item.published_at), item.source].filter(Boolean).join(" · ");
      const tickers = (item.tickers ?? []).slice(0, 3).join(", ");
      return (
        <Pressable
          onPress={() => openStory(item.url)}
          disabled={!href}
          accessibilityRole="button"
          accessibilityLabel={`${item.headline}. ${meta}${href ? ". Opens in browser." : ""}`}
          style={({ pressed }) => [styles.row, pressed && href ? { backgroundColor: colors.hover } : null]}
        >
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={{ fontWeight: "600", lineHeight: 20 }} numberOfLines={3}>
              {item.headline}
            </Text>
            <View style={styles.metaRow}>
              {meta ? <Text variant="muted">{meta}</Text> : null}
              {tickers ? (
                <Text variant="mono" style={{ fontSize: 11, color: colors.textSecondary }}>
                  {tickers}
                </Text>
              ) : null}
            </View>
          </View>
          {href ? <ExternalLink color={colors.textMuted} size={16} /> : null}
        </Pressable>
      );
    },
    [styles, colors, openStory],
  );

  return (
    <GlassScreen>
      <Stack.Screen options={{ headerShown: false }} />
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            hitSlop={12}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <ArrowLeft color={colors.textPrimary} size={22} />
          </Pressable>
          <Text variant="display" style={{ fontFamily: AVENIR }}>
            Market News
          </Text>
        </View>

        <FlatList
          data={isPending ? [] : items}
          keyExtractor={(n) => String(n.id)}
          renderItem={renderItem}
          ItemSeparatorComponent={() => <View style={styles.sep} />}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            isPending ? (
              <Card style={styles.center}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading news" />
              </Card>
            ) : isError ? (
              <Card style={styles.center}>
                <Text variant="secondary">Could not load news.</Text>
                <Button title="Retry" variant="outline" onPress={() => refetch()} />
              </Card>
            ) : (
              <Card style={styles.center}>
                <Text variant="secondary">No news yet.</Text>
                <Text variant="muted" style={{ textAlign: "center" }}>
                  Latest PSX headlines will appear here.
                </Text>
              </Card>
            )
          }
        />
      </SafeAreaView>
    </GlassScreen>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    header: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
    backBtn: { minWidth: 44, minHeight: 44, alignItems: "center", justifyContent: "center", marginLeft: -10 },
    list: { paddingHorizontal: 16, paddingBottom: 28, flexGrow: 1 },
    row: { flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 14, minHeight: 44, borderRadius: 8, paddingHorizontal: 4 },
    metaRow: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" },
    sep: { height: StyleSheet.hairlineWidth, backgroundColor: c.border },
    center: { alignItems: "center", gap: 10, paddingVertical: 28, marginTop: 8 },
  });
