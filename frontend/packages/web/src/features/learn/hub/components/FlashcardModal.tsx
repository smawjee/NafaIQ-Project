import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Check, Layers, X, RotateCcw, PartyPopper } from "lucide-react";
import { FLASHCARDS } from "@/lib/learn/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function FlashcardModal({
  onClose,
  cards = FLASHCARDS,
}: {
  onClose: () => void;
  cards?: Array<{ front: string; def?: string; back?: string; ur?: string }>;
}) {
  const { t } = useLang();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [deck, setDeck] = useState(cards.map((_, i) => i));
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const total = cards.length;
  const done = pos >= deck.length;
  const card = !done ? cards[deck[pos]] : null;
  const reviewed = total - (deck.length - pos);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const firstControl = dialog?.querySelector<HTMLElement>("button:not([disabled])");
    (firstControl ?? dialog)?.focus();

    return () => previouslyFocused?.focus();
  }, []);

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const controls = Array.from(
      dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    );
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function next() {
    setFlipped(false);
    setPos((p) => p + 1);
  }
  function reviewAgain() {
    setFlipped(false);
    setDeck((d) => [...d, d[pos]]);
    setPos((p) => p + 1);
  }
  function restart() {
    setDeck(cards.map((_, i) => i));
    setPos(0);
    setFlipped(false);
  }

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="flashcards-dialog-title"
      tabIndex={-1}
      onKeyDown={handleDialogKeyDown}
      className="fixed inset-0 z-50 flex flex-col bg-background p-4 outline-none"
    >
      <div className="flex items-center justify-between">
        <span
          id="flashcards-dialog-title"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-primary"
        >
          <Layers className="h-4 w-4" strokeWidth={1.5} /> {t("Flashcards")}
        </span>
        <button onClick={onClose} aria-label={t("Close")}>
          <X className="h-5 w-5 text-text-secondary" />
        </button>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-6">
        {card ? (
          <>
            <button
              onClick={() => setFlipped((f) => !f)}
              className="flip-card h-72 w-full max-w-md"
              aria-label={t("Flip card")}
            >
              <div className={cn("flip-inner", flipped && "flipped")}>
                <div className="flip-face rounded-[16px] border border-border bg-surface p-8">
                  <div className="text-2xl font-bold text-text-primary">{t(card.front)}</div>
                  {card.ur && <div className="mt-3 font-urdu text-3xl text-bull">{card.ur}</div>}
                  <div className="mt-6 text-xs text-text-muted">{t("Tap to flip")}</div>
                </div>
                <div className="flip-face flip-back rounded-[16px] border border-bull/40 bg-surface p-8 text-center">
                  <p className="text-sm leading-relaxed text-text-secondary">
                    {t(card.back ?? card.def ?? "")}
                  </p>
                </div>
              </div>
            </button>

            <div className="flex items-center gap-3">
              <button
                onClick={next}
                className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
              >
                <Check className="h-4 w-4" strokeWidth={1.5} /> {t("Got it")}
              </button>
              <button
                onClick={reviewAgain}
                className="inline-flex items-center gap-1.5 rounded-[8px] border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
              >
                <RotateCcw className="h-4 w-4" /> {t("Review Again")}
              </button>
            </div>
            <div className="font-mono text-xs text-text-muted">
              {Math.min(reviewed + 1, total)} / {total} {t("terms")}
            </div>
          </>
        ) : (
          <div className="text-center">
            <PartyPopper className="mx-auto h-10 w-10 text-bull" strokeWidth={1.5} />
            <div className="mt-3 text-lg font-semibold text-text-primary">
              {t("Deck Complete!")}
            </div>
            <div className="mt-1 text-sm text-text-secondary">
              {t("You reviewed all")} {total} {t("terms.")}
            </div>
            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                onClick={restart}
                className="rounded-[8px] bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
              >
                {t("Restart Deck")}
              </button>
              <button
                onClick={onClose}
                className="rounded-[8px] border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
              >
                {t("Exit")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
