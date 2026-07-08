// Learn tab stack: hub (index) + lesson detail. Mirrors web nested /learn routes.
import { Stack } from "expo-router";

import { colors } from "@/constants/theme";

export default function LearnLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="index" />
      <Stack.Screen name="lesson/[id]" />
    </Stack>
  );
}
