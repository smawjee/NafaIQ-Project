// Rotate the password of the signed-in account.
//
// The current password is re-checked before anything changes. Without that, an
// unattended unlocked phone is enough to take the account over permanently — a
// session is a weaker thing to trust than the password itself.
import { useState } from "react";
import { Alert, StyleSheet, View } from "react-native";

import { PasswordField, PrimaryButton } from "@/components/auth/auth-fields";
import { GlassCard } from "@/components/glass/GlassCard";
import { Text } from "@/components/ui";
import { colors } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import { setNewPassword, verifyCurrentPassword } from "@/lib/auth/recovery";
import { KeyRound } from "@/lib/icons";

const MIN_PASSWORD_LENGTH = 8;

export function ChangePasswordCard({ email, style }: { email: string; style?: object }) {
  const { t } = useLang();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (busy) return;

    if (next.length < MIN_PASSWORD_LENGTH) {
      Alert.alert(t("Password must be at least 8 characters."));
      return;
    }
    if (next !== confirm) {
      Alert.alert(t("Those passwords don't match."));
      return;
    }
    if (next === current) {
      Alert.alert(t("Your new password must be different from your current one."));
      return;
    }

    setBusy(true);
    try {
      const check = await verifyCurrentPassword(email, current);
      if (check.error) {
        Alert.alert(t("Current password is incorrect."));
        return;
      }

      const { error } = await setNewPassword(next);
      if (error) {
        Alert.alert(t("Could not update password"), error);
        return;
      }

      setCurrent("");
      setNext("");
      setConfirm("");
      Alert.alert(t("Password updated. Other devices have been signed out."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <GlassCard style={style}>
      <View style={styles.header}>
        <KeyRound color={colors.primary} size={16} />
        <Text variant="title" style={{ fontSize: 15 }}>
          {t("Password")}
        </Text>
      </View>
      <Text variant="secondary" style={styles.blurb}>
        {t("Changing your password signs you out everywhere else.")}
      </Text>

      <View style={styles.form}>
        <PasswordField
          label={t("Current password")}
          value={current}
          onChangeText={setCurrent}
          autoComplete="current-password"
        />
        <PasswordField
          label={t("New password")}
          value={next}
          onChangeText={setNext}
          autoComplete="new-password"
        />
        <PasswordField
          label={t("Confirm new password")}
          value={confirm}
          onChangeText={setConfirm}
          autoComplete="new-password"
        />
        <PrimaryButton label={t("Update password")} onPress={() => void submit()} loading={busy} />
      </View>
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  blurb: { fontSize: 13, marginTop: 4 },
  form: { gap: 12, marginTop: 12 },
});
