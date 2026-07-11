import { useRouterState } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { LEARNING_PATHS, LESSON_CONTENT } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { LABELS } from "@/components/layout/layout.data";

export function Breadcrumbs() {
  const { t } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const segments = path.split("/").filter(Boolean);
  if (segments.length < 2) return null;

  // Special-case lesson pages: /learn/lesson/$id -> Learn Hub > <Path> > <Lesson title>
  let crumbs: { href: string; label: string; last: boolean }[];
  if (segments[0] === "learn" && segments[1] === "lesson" && segments[2]) {
    const id = decodeURIComponent(segments[2]);
    const lesson = LESSON_CONTENT[id];
    const pathName = LEARNING_PATHS.find((p) => p.lessonIds.includes(id))?.title ?? "Lessons";
    crumbs = [
      { href: "/learn", label: "Learn Hub", last: false },
      { href: "/learn", label: pathName, last: false },
      {
        href: path,
        label: lesson?.title ?? id.toUpperCase(),
        last: true,
      },
    ];
  } else {
    crumbs = segments.map((seg, i) => {
      const href = "/" + segments.slice(0, i + 1).join("/");
      const isParam = !LABELS[seg];
      const label = isParam ? decodeURIComponent(seg).toUpperCase() : LABELS[seg];
      return { href, label, last: i === segments.length - 1 };
    });
  }
  return (
    <nav aria-label="Breadcrumb" className="border-b border-white/[0.04] px-3 py-2 sm:px-5 lg:px-6">
      <ol className="mx-auto flex max-w-7xl items-center gap-1.5 text-[12px]">
        {crumbs.map((c, i) => (
          <li key={c.href} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3 w-3 text-text-muted" />}
            {c.last ? (
              <span className="font-medium text-text-primary">{t(c.label)}</span>
            ) : (
              <span className="text-text-secondary">{t(c.label)}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
