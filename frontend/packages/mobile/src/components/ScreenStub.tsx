// Scaffold placeholder: renders a screen's title plus the checklist of sections
// to build (pulled from the web-app inventory). Replace with real UI per screen.
import { Screen } from "@/components/Screen";
import { Card, Text } from "@/components/ui";
import { colors } from "@/constants/theme";

export function ScreenStub({
  title,
  subtitle,
  webRef,
  sections,
}: {
  title: string;
  subtitle?: string;
  webRef: string;
  sections: string[];
}) {
  return (
    <Screen title={title} subtitle={subtitle}>
      <Card style={{ gap: 8 }}>
        <Text variant="muted">Parity reference</Text>
        <Text variant="mono" style={{ color: colors.primary }}>
          {webRef}
        </Text>
      </Card>
      <Card style={{ gap: 10 }}>
        <Text variant="title">Sections to build</Text>
        {sections.map((s) => (
          <Text key={s} variant="secondary">
            ▢ {s}
          </Text>
        ))}
      </Card>
    </Screen>
  );
}
