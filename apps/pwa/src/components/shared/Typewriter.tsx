import { useEffect, useRef, useState } from "react";

/**
 * Streams `text` in character-by-character (typewriter effect) whenever it
 * mounts or the text changes (~18ms per character). Shows a blinking caret
 * while typing.
 */
export function Typewriter({
  text,
  id,
  speed = 18,
  className,
}: {
  text: string;
  id?: string;
  speed?: number;
  className?: string;
}) {
  const [shown, setShown] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setShown("");
    let i = 0;
    timerRef.current = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, speed);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [text, speed]);

  const done = shown.length >= text.length;

  return (
    <span className={className}>
      {shown}
      {!done && (
        <span className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] animate-pulse bg-current align-middle" />
      )}
    </span>
  );
}
