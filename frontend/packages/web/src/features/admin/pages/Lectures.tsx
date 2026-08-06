/**
 * LearnHub lecture management.
 *
 * The official catalogue historically lived only in the frontend bundle
 * (src/lib/learn/data.ts), so adding a lecture meant a redeploy. Rows created
 * here are stored in learnhub_lectures and merged into the Learn Hub at read
 * time, so a new lecture is live immediately.
 *
 * Archiving is offered next to deleting because it is reversible and keeps the
 * audit trail readable; deleting is the true "remove" and is confirmed.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, Archive, ArchiveRestore } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { Lecture, LectureInput } from "@/features/admin/data/types";
import {
  Badge,
  Button,
  DataTable,
  Drawer,
  EmptyBlock,
  ErrorBlock,
  Field,
  formatPkt,
  Input,
  PageHeader,
  Panel,
  PanelSkeleton,
  SearchInput,
  Select,
  StatusBadge,
  Textarea,
  type Column,
} from "@/features/admin/components/ui";

const LEVELS = ["Beginner", "Intermediate", "Advanced"] as const;
const STATUSES = ["draft", "published", "archived"] as const;
const TYPES = ["article", "video"] as const;

/** A blank lecture. Slug is derived from the title until the admin edits it. */
const BLANK: LectureInput = {
  slug: "",
  title: "",
  subtitle: "",
  category: "PSX Basics",
  level: "Beginner",
  duration: "5 min",
  emoji: "📘",
  accent: "#00d4aa",
  type: "article",
  video_url: "",
  sections: [],
  quiz: [],
  status: "published",
  sort_order: 100,
};

/** Mirrors the DB CHECK on slug so the admin sees the problem before the 422. */
function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

export function AdminLectures() {
  const { t } = useLang();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();
  const canWrite = can("learn.write");

  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [editing, setEditing] = useState<Lecture | null>(null);
  const [creating, setCreating] = useState(false);

  const q = useQuery({
    queryKey: ["admin-lectures"],
    queryFn: () => adminApi.listLectures(),
    staleTime: 20_000,
  });

  function invalidate() {
    void qc.invalidateQueries({ queryKey: ["admin-lectures"] });
    void qc.invalidateQueries({ queryKey: ["admin-audit"] });
    // The learner-facing catalogue reads the same rows.
    void qc.invalidateQueries({ queryKey: ["learn-lectures"] });
  }

  const createMut = useMutation({
    mutationFn: (body: LectureInput) => adminApi.createLecture(body),
    onSuccess: () => {
      toast.success(t("Lecture created"));
      setCreating(false);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: (v: { id: string; body: LectureInput }) => adminApi.updateLecture(v.id, v.body),
    onSuccess: () => {
      toast.success(t("Lecture updated"));
      setEditing(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (v: { id: string; reason?: string }) => adminApi.deleteLecture(v.id, v.reason),
    onSuccess: () => {
      toast.success(t("Lecture deleted"));
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rows = useMemo(() => {
    const term = filter.trim().toLowerCase();
    return (q.data ?? []).filter(
      (l) =>
        (!statusFilter || l.status === statusFilter) &&
        (!term ||
          l.title.toLowerCase().includes(term) ||
          l.slug.toLowerCase().includes(term) ||
          l.category.toLowerCase().includes(term)),
    );
  }, [q.data, filter, statusFilter]);

  const columns = useMemo<Column<Lecture>[]>(
    () => [
      {
        id: "title",
        header: t("Lecture"),
        hideable: false,
        exportValue: (r) => r.title,
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2">
            <span aria-hidden>{r.emoji}</span>
            <div className="min-w-0">
              <div className="truncate font-medium text-text-primary">{r.title}</div>
              <code className="truncate text-[11px] text-text-muted">{r.slug}</code>
            </div>
          </div>
        ),
      },
      {
        id: "category",
        header: t("Category"),
        secondary: true,
        exportValue: (r) => r.category,
        cell: (r) => <span className="text-text-secondary">{t(r.category)}</span>,
      },
      {
        id: "level",
        header: t("Level"),
        exportValue: (r) => r.level,
        cell: (r) => <Badge tone="neutral">{t(r.level)}</Badge>,
      },
      {
        id: "type",
        header: t("Type"),
        secondary: true,
        exportValue: (r) => r.type,
        cell: (r) => <span className="text-text-secondary">{t(r.type)}</span>,
      },
      {
        id: "status",
        header: t("Status"),
        exportValue: (r) => r.status,
        cell: (r) => <StatusBadge status={r.status} />,
      },
      {
        id: "updated",
        header: t("Updated"),
        secondary: true,
        exportValue: (r) => r.updated_at ?? "",
        cell: (r) => (
          <span className="whitespace-nowrap text-text-muted">{formatPkt(r.updated_at)}</span>
        ),
      },
      {
        id: "actions",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) =>
          canWrite ? (
            <div className="flex items-center justify-end gap-1">
              <Button size="sm" variant="ghost" onClick={() => setEditing(r)}>
                <Pencil className="h-3.5 w-3.5" />
                <span className="sr-only">{t("Edit lecture")}</span>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  confirm({
                    title:
                      r.status === "archived"
                        ? t("Restore this lecture?")
                        : t("Archive this lecture?"),
                    description:
                      r.status === "archived"
                        ? t("It becomes visible to learners again straight away.")
                        : t(
                            "Learners stop seeing it immediately. The row and its content are kept, so this is reversible.",
                          ),
                    confirmText: r.status === "archived" ? t("Restore") : t("Archive"),
                    variant: r.status === "archived" ? "default" : "destructive",
                    onConfirm: async () =>
                      updateMut.mutate({
                        id: r.id,
                        body: { status: r.status === "archived" ? "published" : "archived" },
                      }),
                  })
                }
              >
                {r.status === "archived" ? (
                  <ArchiveRestore className="h-3.5 w-3.5" />
                ) : (
                  <Archive className="h-3.5 w-3.5" />
                )}
                <span className="sr-only">
                  {r.status === "archived" ? t("Restore lecture") : t("Archive lecture")}
                </span>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  confirm({
                    title: t("Delete this lecture?"),
                    description: t(
                      "The lecture and its content are removed permanently. Archive instead if you may want it back — that is reversible.",
                    ),
                    confirmText: t("Delete"),
                    variant: "destructive",
                    onConfirm: async () => deleteMut.mutate({ id: r.id }),
                  })
                }
              >
                <Trash2 className="h-3.5 w-3.5 text-bear" />
                <span className="sr-only">{t("Delete lecture")}</span>
              </Button>
            </div>
          ) : null,
      },
    ],
    [t, canWrite, confirm, updateMut, deleteMut],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Lectures")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Lectures") }]}
        description={t(
          "The Learn Hub catalogue. A lecture added here is live for learners immediately — no deploy. Every create, edit, archive and delete is written to the audit log.",
        )}
        meta={q.data && <Badge tone="neutral">{q.data.length}</Badge>}
        actions={
          <>
            <SearchInput
              value={filter}
              onChange={setFilter}
              placeholder={t("Filter lectures…")}
              className="w-full sm:w-56"
            />
            <Select
              value={statusFilter}
              aria-label={t("Status")}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-auto min-w-[9rem]"
            >
              <option value="">{t("All statuses")}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(s)}
                </option>
              ))}
            </Select>
            {canWrite && (
              <Button
                variant="primary"
                icon={<Plus className="h-3.5 w-3.5" />}
                onClick={() => setCreating(true)}
              >
                {t("New lecture")}
              </Button>
            )}
          </>
        }
      />

      {!canWrite && (
        <div className="rounded-xl border border-border bg-surface-alt px-4 py-3 text-sm text-text-muted">
          {t(
            "You have read-only access to the lecture catalogue. Editing requires the learn.write permission.",
          )}
        </div>
      )}

      {q.isLoading ? (
        <Panel>
          <PanelSkeleton lines={6} />
        </Panel>
      ) : q.isError ? (
        <Panel>
          <ErrorBlock onRetry={() => void q.refetch()} />
        </Panel>
      ) : (
        <Panel flush>
          <DataTable
            label={t("Lectures")}
            columns={columns}
            rows={rows}
            getRowId={(r) => r.id}
            emptyState={
              <EmptyBlock
                label={t("No lectures yet")}
                hint={t(
                  "The Learn Hub still shows its built-in catalogue. Add a lecture here to extend it.",
                )}
              />
            }
          />
        </Panel>
      )}

      <LectureEditor
        open={creating}
        onOpenChange={(o) => !o && setCreating(false)}
        initial={BLANK}
        saving={createMut.isPending}
        onSave={(body) => createMut.mutate(body)}
      />
      <LectureEditor
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
        initial={editing ?? BLANK}
        existing={!!editing}
        saving={updateMut.isPending}
        onSave={(body) => editing && updateMut.mutate({ id: editing.id, body })}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function LectureEditor({
  open,
  onOpenChange,
  initial,
  existing,
  saving,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: LectureInput;
  existing?: boolean;
  saving: boolean;
  onSave: (body: LectureInput) => void;
}) {
  const { t } = useLang();
  // Keyed remount (see the `key` on the caller) would be heavier than this:
  // the draft resets whenever the drawer is opened on a different lecture.
  const [draft, setDraft] = useState<LectureInput>(initial);
  const [lastInitial, setLastInitial] = useState(initial);
  if (initial !== lastInitial) {
    setLastInitial(initial);
    setDraft(initial);
  }

  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof LectureInput>(key: K, value: LectureInput[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function submit() {
    const title = (draft.title ?? "").trim();
    if (!title) return setError(t("A lecture needs a title."));
    // Derive the slug on create when the admin left it blank, so the common
    // path is one field shorter.
    const slug = (draft.slug ?? "").trim() || slugify(title);
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug)) {
      return setError(t("The slug may only contain lowercase letters, numbers and hyphens."));
    }
    if (draft.type === "video" && !(draft.video_url ?? "").trim()) {
      return setError(t("A video lecture needs a video URL."));
    }
    setError(null);
    onSave({ ...draft, title, slug, video_url: (draft.video_url ?? "").trim() || null });
  }

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={existing ? t("Edit lecture") : t("New lecture")}
      description={t("Learners see this in the Learn Hub as soon as it is published.")}
      footer={
        <>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            {t("Cancel")}
          </Button>
          <Button variant="primary" onClick={submit} loading={saving}>
            {existing ? t("Save changes") : t("Create lecture")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <p className="text-sm text-bear">{error}</p>}

        <Field label={t("Title")} htmlFor="lec-title">
          <Input
            id="lec-title"
            value={draft.title ?? ""}
            onChange={(e) => set("title", e.target.value)}
          />
        </Field>

        <Field
          label={t("Slug")}
          htmlFor="lec-slug"
          hint={t("Used in the lesson URL. Leave blank to derive it from the title.")}
        >
          <Input
            id="lec-slug"
            value={draft.slug ?? ""}
            onChange={(e) => set("slug", e.target.value)}
            placeholder={slugify(draft.title ?? "")}
          />
        </Field>

        <Field label={t("Subtitle")} htmlFor="lec-subtitle">
          <Input
            id="lec-subtitle"
            value={draft.subtitle ?? ""}
            onChange={(e) => set("subtitle", e.target.value)}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("Category")} htmlFor="lec-category">
            <Input
              id="lec-category"
              value={draft.category ?? ""}
              onChange={(e) => set("category", e.target.value)}
            />
          </Field>
          <Field label={t("Level")} htmlFor="lec-level">
            <Select
              id="lec-level"
              value={draft.level ?? "Beginner"}
              onChange={(e) => set("level", e.target.value as LectureInput["level"])}
            >
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {t(l)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("Duration")} htmlFor="lec-duration">
            <Input
              id="lec-duration"
              value={draft.duration ?? ""}
              onChange={(e) => set("duration", e.target.value)}
            />
          </Field>
          <Field label={t("Emoji")} htmlFor="lec-emoji">
            <Input
              id="lec-emoji"
              value={draft.emoji ?? ""}
              onChange={(e) => set("emoji", e.target.value)}
            />
          </Field>
          <Field label={t("Type")} htmlFor="lec-type">
            <Select
              id="lec-type"
              value={draft.type ?? "article"}
              onChange={(e) => set("type", e.target.value as LectureInput["type"])}
            >
              {TYPES.map((ty) => (
                <option key={ty} value={ty}>
                  {t(ty)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("Status")} htmlFor="lec-status">
            <Select
              id="lec-status"
              value={draft.status ?? "published"}
              onChange={(e) => set("status", e.target.value as LectureInput["status"])}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(s)}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {draft.type === "video" && (
          <Field label={t("Video URL")} htmlFor="lec-video">
            <Input
              id="lec-video"
              value={draft.video_url ?? ""}
              onChange={(e) => set("video_url", e.target.value)}
            />
          </Field>
        )}

        <Field
          label={t("Lesson body")}
          htmlFor="lec-sections"
          hint={t(
            'JSON array of sections: [{ "id": "intro", "heading": "Introduction", "blocks": [{ "type": "p", "text": "…" }] }]',
          )}
          error={undefined}
        >
          <JsonArea
            id="lec-sections"
            value={draft.sections ?? []}
            onChange={(v) => set("sections", v)}
          />
        </Field>

        <Field
          label={t("Quiz")}
          htmlFor="lec-quiz"
          hint={t(
            'JSON array of questions: [{ "q": "…", "options": ["…"], "correct": 0, "explanation": "…" }]',
          )}
        >
          <JsonArea id="lec-quiz" value={draft.quiz ?? []} onChange={(v) => set("quiz", v)} />
        </Field>

        <Field
          label={t("Sort order")}
          htmlFor="lec-sort"
          hint={t("Lower numbers appear first in the catalogue.")}
        >
          <Input
            id="lec-sort"
            inputMode="numeric"
            value={String(draft.sort_order ?? 100)}
            onChange={(e) => set("sort_order", Number(e.target.value) || 0)}
          />
        </Field>
      </div>
    </Drawer>
  );
}

/**
 * JSON editor for the two array columns. Invalid JSON is shown inline and the
 * last valid value is kept, so a typo mid-edit cannot silently blank the body.
 */
function JsonArea({
  id,
  value,
  onChange,
}: {
  id: string;
  value: unknown;
  onChange: (v: unknown[]) => void;
}) {
  const { t } = useLang();
  const [text, setText] = useState(() => JSON.stringify(value ?? [], null, 2));
  const [seen, setSeen] = useState(value);
  const [bad, setBad] = useState(false);

  if (value !== seen) {
    setSeen(value);
    setText(JSON.stringify(value ?? [], null, 2));
    setBad(false);
  }

  return (
    <div className="space-y-1">
      <Textarea
        id={id}
        rows={6}
        value={text}
        spellCheck={false}
        dir="ltr"
        onChange={(e) => {
          const next = e.target.value;
          setText(next);
          try {
            const parsed = JSON.parse(next || "[]");
            if (!Array.isArray(parsed)) throw new Error("not an array");
            setBad(false);
            onChange(parsed);
          } catch {
            setBad(true);
          }
        }}
      />
      {bad && (
        <p className="text-xs text-bear">{t("Not valid JSON — the last valid value is kept.")}</p>
      )}
    </div>
  );
}
