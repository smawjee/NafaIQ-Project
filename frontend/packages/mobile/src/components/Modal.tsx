// Themed bottom-sheet modal + labelled Field input. RN equivalent of the web
// Modal.tsx (used by goal-contribution, add-holding, etc.).
import { type ReactNode } from "react";
import { Modal as RNModal, Pressable, StyleSheet, TextInput, View } from "react-native";

import { Text } from "@/components/ui";
import { radii } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { X } from "@/lib/icons";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const { colors } = useTheme();
  return (
    <RNModal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.wrap}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
        <View style={[styles.sheet, { backgroundColor: colors.glassFillStrong, borderColor: colors.border }]}>
          <View style={styles.header}>
            <Text variant="title">{title}</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
              <X color={colors.textMuted} size={20} />
            </Pressable>
          </View>
          {children}
        </View>
      </View>
    </RNModal>
  );
}

export function Field({
  label,
  ...props
}: { label: string } & React.ComponentProps<typeof TextInput>) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: 4 }}>
      {label ? <Text variant="secondary">{label}</Text> : null}
      <TextInput
        placeholderTextColor={colors.textMuted}
        accessibilityLabel={label}
        style={[styles.field, { borderColor: colors.input, color: colors.textPrimary, backgroundColor: colors.glassFill }]}
        {...props}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { borderTopLeftRadius: radii.modal, borderTopRightRadius: radii.modal, borderTopWidth: 1, padding: 20, gap: 12 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  field: { minHeight: 44, borderWidth: 1, borderRadius: radii.btn, paddingHorizontal: 12 },
});
