import { Link, useParams } from "@tanstack/react-router";
import { Inbox } from "lucide-react";
import { useLessonCatalogue } from "@/hooks/learn/use-lectures";
import { useLang } from "@/hooks/use-lang";
import { LessonInner } from "@/features/learn/lesson/components/LessonInner";

export function LessonPage() {
  const { id } = useParams({ from: "/learn/lesson/$id" });
  // Static catalogue + lectures added from the admin console.
  const catalogue = useLessonCatalogue();
  const lesson = catalogue[id];
  const { t } = useLang();

  if (!lesson) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <Inbox className="mx-auto h-8 w-8 text-text-muted" strokeWidth={1.5} />
        <h1 className="mt-3 text-lg font-semibold text-text-primary">{t("Lesson not found")}</h1>
        <Link
          to="/learn"
          className="mt-4 inline-block rounded-btn bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground"
        >
          {t("Back to Learn Hub")}
        </Link>
      </div>
    );
  }

  return <LessonInner key={lesson.id} lesson={lesson} />;
}
