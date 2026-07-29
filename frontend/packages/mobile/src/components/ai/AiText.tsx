// Mobile twin of web's components/ai/AiText.tsx. The PARSE is shared
// (@nafaiq/shared) so it cannot drift from the prompt contract; only the render
// differs — RN has no <strong> or <ul>, so bold is a nested <Text> and bullets
// are laid out by hand.
import { View } from "react-native";

import { Text } from "@/components/ui";
import { colors } from "@/constants/theme";
import { parseAiText, type Span } from "@nafaiq/shared";

function renderSpans(items: Span[]) {
  // RN <Text> nests, so a bold run is a child <Text> and inherits the parent's
  // colour/size — do not restyle it here.
  return items.map((s, i) => (
    <Text key={i} style={s.bold ? { fontWeight: "700" } : undefined}>
      {s.text}
    </Text>
  ));
}

/**
 * One tutor chat message. User messages pass through verbatim — only the model
 * is asked for formatting, and a learner typing `**` means `**`.
 */
export function TutorMessage({
  content,
  role,
  color,
}: {
  content: string;
  role: "user" | "assistant";
  color: string;
}) {
  const base = { color, fontSize: 14 } as const;

  if (role === "user") return <Text style={base}>{content}</Text>;

  const blocks = parseAiText(content);

  return (
    <View style={{ gap: 8 }}>
      {blocks.map((b, i) =>
        b.kind === "ul" ? (
          <View key={i} style={{ gap: 4 }}>
            {b.items.map((item, j) => (
              <View key={j} style={{ flexDirection: "row", gap: 6 }}>
                <Text style={{ ...base, color: colors.textMuted }}>{"•"}</Text>
                <Text style={[base, { flex: 1 }]}>{renderSpans(item)}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text key={i} style={base}>
            {renderSpans(b.spans)}
          </Text>
        ),
      )}
    </View>
  );
}
