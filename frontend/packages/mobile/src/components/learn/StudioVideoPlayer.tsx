import { useEvent } from "expo";
import { Image } from "expo-image";
import { useVideoPlayer, VideoView } from "expo-video";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { Text } from "@/components/ui";
import { radii } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { Captions, CaptionsOff } from "@/lib/icons";
import { parseWebVtt, type CaptionCue } from "@/lib/vtt";

export function StudioVideoPlayer({
  url,
  captionsUrl,
  posterUrl,
  title,
}: {
  url: string;
  captionsUrl?: string | null;
  posterUrl?: string | null;
  title: string;
}) {
  const { colors } = useTheme();
  const { t } = useLang();
  const [firstFrame, setFirstFrame] = useState(false);
  const [captionsEnabled, setCaptionsEnabled] = useState(Boolean(captionsUrl));
  const [cues, setCues] = useState<CaptionCue[]>([]);

  const source = useMemo(
    () => ({
      uri: url,
      contentType: "progressive" as const,
      useCaching: false,
      metadata: { title, artist: "NafaIQ LearnHub" },
    }),
    [title, url],
  );
  const player = useVideoPlayer(source, (instance) => {
    instance.timeUpdateEventInterval = 0.25;
  });
  const progress = useEvent(player, "timeUpdate", {
    currentTime: 0,
    bufferedPosition: 0,
    currentLiveTimestamp: null,
    currentOffsetFromLive: null,
  });

  useEffect(() => {
    if (!captionsUrl) {
      setCues([]);
      return;
    }
    let active = true;
    fetch(captionsUrl)
      .then((response) => {
        if (!response.ok) throw new Error("Captions unavailable");
        return response.text();
      })
      .then((text) => {
        if (active) setCues(parseWebVtt(text));
      })
      .catch(() => {
        if (active) setCues([]);
      });
    return () => {
      active = false;
    };
  }, [captionsUrl]);

  const activeCue = captionsEnabled
    ? cues.find((cue) => progress.currentTime >= cue.start && progress.currentTime <= cue.end)
    : undefined;

  return (
    <View style={[styles.shell, { borderColor: colors.border, backgroundColor: "#000" }]}>
      <VideoView
        player={player}
        style={styles.video}
        nativeControls
        contentFit="contain"
        fullscreenOptions={{ enable: true }}
        onFirstFrameRender={() => setFirstFrame(true)}
        accessibilityLabel={`${title} ${t("video lesson")}`}
      />
      {!firstFrame && posterUrl ? (
        <Image
          source={{ uri: posterUrl }}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          accessibilityLabel={t("Video preview")}
        />
      ) : null}
      {activeCue ? (
        <View pointerEvents="none" style={styles.captionWrap}>
          <Text style={styles.captionText}>{activeCue.text}</Text>
        </View>
      ) : null}
      {captionsUrl ? (
        <Pressable
          onPress={() => setCaptionsEnabled((value) => !value)}
          style={[styles.captionButton, { backgroundColor: colors.surface + "e6" }]}
          accessibilityRole="button"
          accessibilityLabel={captionsEnabled ? t("Turn captions off") : t("Turn captions on")}
          accessibilityState={{ selected: captionsEnabled }}
        >
          {captionsEnabled ? (
            <Captions color={colors.primary} size={18} />
          ) : (
            <CaptionsOff color={colors.textMuted} size={18} />
          )}
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    width: "100%",
    aspectRatio: 16 / 9,
    borderRadius: radii.card,
    borderWidth: 1,
    overflow: "hidden",
  },
  video: { width: "100%", height: "100%" },
  captionWrap: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 42,
    alignItems: "center",
  },
  captionText: {
    color: "#fff",
    backgroundColor: "rgba(0,0,0,0.78)",
    borderRadius: 6,
    paddingHorizontal: 9,
    paddingVertical: 5,
    textAlign: "center",
    fontSize: 13,
    lineHeight: 18,
  },
  captionButton: {
    position: "absolute",
    top: 10,
    right: 10,
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
});
