import { FormEvent, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { BookOpen, FileText, FileUp, Loader2, Sparkles, Trash2 } from "lucide-react";
import type { StudioLevel } from "@nafaiq/shared";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import {
  useCreateStudioPdfProject,
  useCreateStudioProject,
  useDeleteStudioProject,
  useStudioProjects,
  useStudioStatus,
} from "@/hooks/learn/use-learn-studio";

export function StudioCreateCard() {
  const { user } = useAuth();
  const { lang, t } = useLang();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const create = useCreateStudioProject();
  const createPdf = useCreateStudioPdfProject();
  const removeProject = useDeleteStudioProject();
  const status = useStudioStatus(Boolean(user));
  const projects = useStudioProjects(Boolean(user) && Boolean(status.data?.enabled));
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<"topic" | "pdf">("topic");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfFocus, setPdfFocus] = useState("");
  const [pdfFileError, setPdfFileError] = useState("");
  const [level, setLevel] = useState<StudioLevel>("beginner");

  const disabledForBackend = Boolean(user && status.data && !status.data.enabled);

  async function submitTopic(event: FormEvent) {
    event.preventDefault();
    if (!user) {
      navigate({ to: "/auth" });
      return;
    }
    const value = topic.trim();
    if (value.length < 3) return;
    const project = await create.mutateAsync({ topic: value, lang, level, targetMinutes: 4 });
    navigate({ to: "/learn/generated/$projectId", params: { projectId: project.id } });
  }

  async function submitPdf(event: FormEvent) {
    event.preventDefault();
    if (!user) {
      navigate({ to: "/auth" });
      return;
    }
    if (!pdfFile) return;
    const project = await createPdf.mutateAsync({
      file: pdfFile,
      filename: pdfFile.name,
      topic: pdfFocus.trim(),
      lang,
      level,
      targetMinutes: 4,
    });
    navigate({ to: "/learn/generated/$projectId", params: { projectId: project.id } });
  }

  return (
    <section
      data-testid="studio-create-card"
      className="overflow-hidden rounded-card border border-ai/25 bg-gradient-to-br from-ai/10 via-surface to-surface p-5 max-sm:pr-[4.75rem] sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-btn border border-ai/25 bg-ai/10 text-ai">
          <Sparkles className="h-5 w-5" strokeWidth={1.5} />
        </span>
        <div>
          <h2 className="text-base font-semibold text-text-primary">
            {t("Create your own PSX lesson")}
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">
            {t(
              "Enter a PSX topic to create source-grounded notes, flashcards, a quiz, and an optional video lecture.",
            )}
          </p>
          {disabledForBackend ? (
            <p className="mt-2 rounded-btn border border-warning/25 bg-warning/10 px-3 py-2 text-xs font-medium text-warning">
              {t("LearnHub Studio is installed, but disabled on this backend. Enable LEARN_STUDIO_ENABLED and restart the API.")}
            </p>
          ) : null}
        </div>
      </div>

      <div
        className="mt-5 inline-flex rounded-btn border border-border bg-elevated p-1"
        role="group"
        aria-label={t("Lesson source")}
      >
        <button
          type="button"
          aria-pressed={mode === "topic"}
          onClick={() => !disabledForBackend && setMode("topic")}
          disabled={disabledForBackend}
          className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold ${mode === "topic" ? "bg-bull text-bull-foreground" : "text-text-secondary"}`}
        >
          <BookOpen className="mr-1.5 inline h-3.5 w-3.5" /> {t("Choose a topic")}
        </button>
        <button
          type="button"
          aria-pressed={mode === "pdf"}
          onClick={() => !disabledForBackend && setMode("pdf")}
          disabled={disabledForBackend}
          className={`rounded-[6px] px-3 py-1.5 text-xs font-semibold ${mode === "pdf" ? "bg-bull text-bull-foreground" : "text-text-secondary"}`}
        >
          <FileUp className="mr-1.5 inline h-3.5 w-3.5" /> {t("Upload a PDF")}
        </button>
      </div>

      {mode === "topic" ? (
        <form
          key="topic"
          onSubmit={submitTopic}
          className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_160px_auto]"
        >
          <label className="sr-only" htmlFor="studio-topic">
            {t("PSX lesson topic")}
          </label>
          <input
            id="studio-topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            maxLength={160}
            placeholder={t("e.g. How dividends work on PSX")}
            className="min-h-11 rounded-btn border border-border bg-elevated px-4 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-ai"
          />
          <label className="sr-only" htmlFor="studio-level">
            {t("Difficulty")}
          </label>
          <select
            id="studio-level"
            value={level}
            onChange={(event) => setLevel(event.target.value as StudioLevel)}
            className="min-h-11 rounded-btn border border-border bg-elevated px-3 text-sm text-text-primary outline-none focus:border-ai"
          >
            <option value="beginner">{t("Beginner")}</option>
            <option value="intermediate">{t("Intermediate")}</option>
            <option value="advanced">{t("Advanced")}</option>
          </select>
          <button
            type="submit"
            disabled={disabledForBackend || create.isPending || topic.trim().length < 3}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-btn bg-bull px-5 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {create.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <BookOpen className="h-4 w-4" />
            )}
            {create.isPending ? t("Creating…") : t("Create lesson")}
          </button>
        </form>
      ) : (
        <form key="pdf" onSubmit={submitPdf} className="mt-4 grid gap-3">
          <label
            htmlFor="studio-pdf"
            className="flex min-h-24 cursor-pointer items-center gap-3 rounded-btn border border-dashed border-ai/40 bg-elevated px-4 py-3 hover:bg-ai/5"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-btn bg-ai/10 text-ai">
              <FileText className="h-5 w-5" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-text-primary">
                {pdfFile?.name ?? t("Select a private PDF")}
              </span>
              <span className="mt-1 block text-[11px] text-text-muted">
                {t("PDF only · Up to 15 MB and 100 pages · Never added to the public corpus")}
              </span>
            </span>
          </label>
          <input
            id="studio-pdf"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              const limit = status.data?.pdfMaxBytes ?? 15 * 1024 * 1024;
              if (selected && selected.size > limit) {
                setPdfFile(null);
                setPdfFileError(t("PDF exceeds the 15 MB limit."));
                event.target.value = "";
              } else {
                setPdfFile(selected);
                setPdfFileError("");
              }
            }}
            className="sr-only"
          />
          {pdfFileError ? (
            <p role="alert" className="text-xs text-bear">
              {pdfFileError}
            </p>
          ) : null}
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_160px_auto]">
            <label className="sr-only" htmlFor="studio-pdf-focus">
              {t("Lesson focus (optional)")}
            </label>
            <input
              id="studio-pdf-focus"
              value={pdfFocus}
              onChange={(event) => setPdfFocus(event.target.value)}
              maxLength={160}
              placeholder={t("Optional focus, e.g. explain the dividend policy")}
              className="min-h-11 rounded-btn border border-border bg-elevated px-4 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-ai"
            />
            <label className="sr-only" htmlFor="studio-pdf-level">
              {t("Difficulty")}
            </label>
            <select
              id="studio-pdf-level"
              value={level}
              onChange={(event) => setLevel(event.target.value as StudioLevel)}
              className="min-h-11 rounded-btn border border-border bg-elevated px-3 text-sm text-text-primary outline-none focus:border-ai"
            >
              <option value="beginner">{t("Beginner")}</option>
              <option value="intermediate">{t("Intermediate")}</option>
              <option value="advanced">{t("Advanced")}</option>
            </select>
            <button
              type="submit"
              disabled={disabledForBackend || createPdf.isPending || !pdfFile}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-btn bg-bull px-5 text-sm font-semibold text-bull-foreground hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createPdf.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileUp className="h-4 w-4" />
              )}
              {createPdf.isPending ? t("Uploading…") : t("Create from PDF")}
            </button>
          </div>
        </form>
      )}

      {(create.isError || createPdf.isError) && (
        <p role="alert" className="mt-3 text-xs text-bear">
          {createPdf.error instanceof Error
            ? createPdf.error.message
            : t("The lesson could not be started. Check your daily allowance and try again.")}
        </p>
      )}
      <p className="mt-3 text-[10px] text-text-muted">
        {t("5 study packs and 1 video per day · Educational content only")}
      </p>

      {projects.data?.projects.length ? (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="text-xs font-semibold text-text-primary">{t("Your generated lessons")}</h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {projects.data.projects.slice(0, 3).map((project) => (
              <div
                key={project.id}
                className="flex rounded-btn border border-border bg-elevated hover:border-ai/40"
              >
                <Link
                  to="/learn/generated/$projectId"
                  params={{ projectId: project.id }}
                  className="min-w-0 flex-1 px-3 py-2.5"
                >
                  <div className="truncate text-xs font-medium text-text-primary">
                    {project.topic}
                  </div>
                  {project.sourceKind === "pdf" && project.documentName ? (
                    <div className="mt-1 truncate text-[10px] text-ai">{project.documentName}</div>
                  ) : null}
                  <div className="mt-1 text-[10px] capitalize text-text-muted">
                    {t(project.stage.replaceAll("_", " "))}
                  </div>
                </Link>
                <button
                  type="button"
                  aria-label={`${t("Delete lesson")}: ${project.topic}`}
                  disabled={removeProject.isPending}
                  onClick={() =>
                    confirm({
                      title: t("Delete lesson"),
                      description: t("Delete this lesson and its private uploaded files?"),
                      confirmText: t("Delete"),
                      cancelText: t("Cancel"),
                      onConfirm: () => removeProject.mutateAsync(project.id),
                      errorMessage: t("The lesson could not be deleted. Please try again."),
                    })
                  }
                  className="m-2 flex h-8 w-8 shrink-0 items-center justify-center rounded-btn text-text-muted hover:bg-bear/10 hover:text-bear disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
