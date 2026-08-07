/**
 * Admin-managed Learn Hub lectures (learnhub_lectures), merged with the static
 * catalogue that ships in the bundle.
 *
 * The static catalogue stays the source of truth for the lessons that shipped
 * with the app; this only *adds* to it. A lecture created in the admin console
 * therefore appears without a redeploy, and a failed fetch degrades to exactly
 * the catalogue users see today rather than an empty Learn Hub.
 */
import { useQuery } from "@tanstack/react-query";
import { fetchLearnLectures, type ApiLearnLecture } from "@/lib/psx/client";
import { LESSON_CONTENT, type LessonContent } from "@/lib/learn/data";

/** Map a DB row onto the shape the existing lesson renderer consumes. */
function toLessonContent(l: ApiLearnLecture): LessonContent {
  return {
    id: l.slug,
    emoji: l.emoji,
    title: l.title,
    subtitle: l.subtitle,
    category: l.category,
    accent: l.accent,
    duration: l.duration,
    level: (l.level as LessonContent["level"]) ?? "Beginner",
    origin: "official",
    type: l.type === "video" ? "video" : "article",
    videoUrl: l.video_url ?? undefined,
    presets: [],
    sections: (l.sections ?? []) as LessonContent["sections"],
    quiz: (l.quiz ?? []) as LessonContent["quiz"],
  };
}

export function useAdminLectures() {
  const q = useQuery({
    queryKey: ["learn-lectures"],
    queryFn: fetchLearnLectures,
    staleTime: 5 * 60_000,
    // The static catalogue already renders, so a lecture fetch failure is not
    // worth retrying hard or surfacing as an error state.
    retry: 1,
  });

  const lectures = (q.data?.lectures ?? []).map(toLessonContent);
  return { lectures, isLoading: q.isLoading };
}

/**
 * Static catalogue plus admin lectures, keyed by lesson id. A static lesson
 * always wins a slug collision — an admin cannot accidentally shadow shipped
 * content by reusing its id.
 */
export function useLessonCatalogue(): Record<string, LessonContent> {
  const { lectures } = useAdminLectures();
  const merged: Record<string, LessonContent> = {};
  for (const l of lectures) merged[l.id] = l;
  return { ...merged, ...LESSON_CONTENT };
}
