import { usePathname } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, TextInput, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { Screen } from "@/components/Screen";
import { Button, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import {
  type BugReportInput,
  type BugReportStatus,
  useCreateBugReport,
  useMyBugReports,
} from "@/hooks/queries/use-support";
import { useTheme } from "@/hooks/use-theme";
import { LifeBuoy, MessageCircleQuestion, ShieldCheck } from "@/lib/icons";

const CATEGORIES: { value: BugReportInput["category"]; label: string }[] = [
  { value: "bug", label: "Broken" },
  { value: "data", label: "Wrong data" },
  { value: "billing", label: "Billing" },
  { value: "feature", label: "Suggestion" },
  { value: "other", label: "Other" },
];

const STATUS: Record<BugReportStatus, string> = {
  open: "Open",
  investigating: "Being looked at",
  resolved: "Resolved",
  wont_fix: "Closed",
};

export default function HelpScreen() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const route = usePathname();
  const reports = useMyBugReports();
  const create = useCreateBugReport();
  const [category, setCategory] = useState<BugReportInput["category"]>("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const valid = title.trim().length >= 3 && description.trim().length >= 10;

  function submit() {
    if (!valid) return;
    create.mutate(
      { title: title.trim(), description: description.trim(), category, route },
      {
        onSuccess: () => {
          setTitle("");
          setDescription("");
          Alert.alert("Report sent", "Thank you. You can track its status below.");
        },
        onError: () => Alert.alert("Could not send report", "Please check your connection and try again."),
      },
    );
  }

  return (
    <Screen title="Help & Support" subtitle="Tell us what happened and follow the response." back>
      <GlassCard style={styles.hero}>
        <View style={styles.iconBox}><LifeBuoy color={colors.primary} size={20} /></View>
        <View style={{ flex: 1, gap: 3 }}>
          <Text variant="title" style={styles.heading}>Report a problem</Text>
          <Text variant="secondary" style={{ fontSize: 13 }}>Your app version and current route are attached automatically.</Text>
        </View>
      </GlassCard>

      <GlassCard style={styles.form}>
        <Text variant="secondary">What kind of problem?</Text>
        <ChipRow
          options={CATEGORIES.map((item) => item.label)}
          value={CATEGORIES.find((item) => item.value === category)?.label ?? "Broken"}
          onChange={(label) => setCategory(CATEGORIES.find((item) => item.label === label)?.value ?? "bug")}
        />
        <Field label="Summary" value={title} onChangeText={setTitle} placeholder="Portfolio total does not match" maxLength={200} colors={colors} />
        <Field
          label="What happened?"
          value={description}
          onChangeText={setDescription}
          placeholder="What you did, what you expected, and what happened instead."
          maxLength={5000}
          multiline
          minHeight={112}
          colors={colors}
        />
        <Text variant="muted">{description.length}/5000 · A sentence or two is enough.</Text>
        <Button title="Send report" onPress={submit} loading={create.isPending} disabled={!valid} icon={<ShieldCheck color={colors.primaryForeground} size={16} />} />
      </GlassCard>

      <Text variant="title" style={styles.heading}>Your previous reports</Text>
      {reports.isPending ? <ActivityIndicator color={colors.primary} /> : reports.isError ? (
        <GlassCard><Text variant="secondary">Could not load your reports.</Text><Button title="Retry" variant="ghost" onPress={() => reports.refetch()} /></GlassCard>
      ) : (reports.data?.length ?? 0) === 0 ? (
        <GlassCard style={styles.empty}><MessageCircleQuestion color={colors.textMuted} size={22} /><Text variant="secondary">No reports yet.</Text></GlassCard>
      ) : reports.data!.slice(0, 10).map((report) => {
        const resolved = report.status === "resolved";
        return (
          <GlassCard key={report.id} style={styles.report}>
            <View style={styles.between}>
              <Text style={{ flex: 1, fontWeight: "700" }} numberOfLines={2}>{report.title}</Text>
              <View style={[styles.status, { borderColor: (resolved ? colors.bull : colors.primary) + "55" }]}>
                <Text style={{ color: resolved ? colors.bull : colors.primary, fontSize: 10, fontWeight: "700" }}>{STATUS[report.status]}</Text>
              </View>
            </View>
            <Text variant="muted">{new Date(report.created_at).toLocaleDateString()}</Text>
            {report.admin_note ? <Text variant="secondary" style={{ fontSize: 13 }}>{report.admin_note}</Text> : null}
          </GlassCard>
        );
      })}
    </Screen>
  );
}

function Field({ label, colors, minHeight, ...props }: { label: string; colors: ThemeColors; minHeight?: number } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={{ gap: 6 }}>
      <Text variant="secondary">{label}</Text>
      <TextInput
        {...props}
        accessibilityLabel={label}
        placeholderTextColor={colors.textMuted}
        style={{ minHeight: minHeight ?? 48, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.glassFill, borderRadius: 10, color: colors.textPrimary, paddingHorizontal: 12, paddingVertical: 10, textAlignVertical: props.multiline ? "top" : "center" }}
      />
    </View>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: 12 },
  iconBox: { width: 42, height: 42, borderRadius: 12, backgroundColor: c.primary + "18", borderWidth: 1, borderColor: c.primary + "44", alignItems: "center", justifyContent: "center" },
  heading: { fontFamily: fonts.headingMedium },
  form: { gap: 12 },
  empty: { alignItems: "center", gap: 8, paddingVertical: 24 },
  report: { gap: 6 },
  between: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 10 },
  status: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4, backgroundColor: c.glassFill },
});
