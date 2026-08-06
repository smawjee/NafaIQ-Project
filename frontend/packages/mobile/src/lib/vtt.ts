export interface CaptionCue {
  start: number;
  end: number;
  text: string;
}

function timestampToSeconds(value: string): number {
  const parts = value.trim().replace(",", ".").split(":").map(Number);
  if (parts.some(Number.isNaN)) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return parts[0] * 60 + parts[1];
}

/** Parse the small, deterministic WEBVTT files emitted by the Studio worker. */
export function parseWebVtt(source: string): CaptionCue[] {
  return source
    .replace(/^\uFEFF/, "")
    .split(/\r?\n\r?\n/)
    .flatMap((block) => {
      const lines = block.split(/\r?\n/).map((line) => line.trim());
      const timingIndex = lines.findIndex((line) => line.includes("-->"));
      if (timingIndex < 0) return [];
      const [startRaw, endRaw] = lines[timingIndex].split("-->");
      const endToken = endRaw?.trim().split(/\s+/)[0];
      if (!startRaw || !endToken) return [];
      const text = lines
        .slice(timingIndex + 1)
        .join("\n")
        .replace(/<[^>]+>/g, "")
        .trim();
      if (!text) return [];
      return [
        {
          start: timestampToSeconds(startRaw),
          end: timestampToSeconds(endToken),
          text,
        },
      ];
    });
}
