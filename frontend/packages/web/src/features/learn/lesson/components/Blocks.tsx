import { Info } from "lucide-react";
import { EmojiIcon } from "@/components/icons/icons";
import { type ContentBlock } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { CALLOUT_META } from "@/features/learn/lesson/lesson.data";

export function Blocks({ blocks, accent }: { blocks: ContentBlock[]; accent: string }) {
  const { t } = useLang();
  return (
    <>
      {blocks.map((b, i) => {
        if (b.type === "p") {
          return (
            <p key={i} className="my-4 text-base leading-[1.9] text-text-secondary">
              {t(b.text)}
            </p>
          );
        }
        if (b.type === "callout") {
          const m = CALLOUT_META[b.kind];
          const isNote = b.kind === "note";
          return (
            <div
              key={i}
              className="my-6 rounded-btn p-4"
              style={{ background: `${m.color}10`, borderInlineStart: `3px solid ${m.color}` }}
            >
              <div
                className="flex items-center gap-1.5 text-xs font-bold"
                style={{ color: m.color }}
              >
                {isNote ? (
                  <Info className="h-3.5 w-3.5" strokeWidth={2} />
                ) : (
                  <EmojiIcon emoji={m.emoji} size={13} />
                )}
                {t(m.label)}
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">{t(b.text)}</p>
            </div>
          );
        }
        if (b.type === "formula") {
          return (
            <div
              key={i}
              className="my-6 rounded-btn border border-border bg-elevated p-5 font-mono text-sm"
            >
              {b.lines.map((line, j) => (
                <div key={j} className="text-bull">
                  {t(line)
                    .split("=")
                    .map((part, k, all) => (
                      <span key={k}>
                        <span className="text-text-primary">{part}</span>
                        {k < all.length - 1 && <span className="text-text-muted"> = </span>}
                      </span>
                    ))}
                </div>
              ))}
            </div>
          );
        }
        // table
        return (
          <div key={i} className="my-6 overflow-x-auto rounded-card border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {b.head.map((h) => (
                    <th
                      key={h}
                      className="border border-border bg-elevated px-3 py-2 text-start font-bold text-text-primary"
                    >
                      {t(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((row, r) => (
                  <tr
                    key={r}
                    className={cn(
                      "transition-colors hover:bg-bull/[0.04]",
                      r % 2 === 0 ? "bg-surface" : "bg-surface-alt",
                    )}
                  >
                    {row.map((cell, c) => (
                      <td key={c} className="border border-border px-3 py-2 text-text-secondary">
                        {t(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}
