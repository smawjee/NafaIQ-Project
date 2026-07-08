import { cn } from "@/lib/utils";

/**
 * AiGlyph — a professional, Gemini-style four-point "spark" mark used to
 * represent AI chat / assistants across the app. Uses currentColor so it
 * inherits text color, and stays crisp at any size.
 */
export function AiGlyph({
  className,
  size,
  strokeWidth = 0,
}: {
  className?: string;
  size?: number;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      stroke={strokeWidth ? "currentColor" : "none"}
      strokeWidth={strokeWidth}
      className={cn("shrink-0", className)}
      aria-hidden="true"
    >
      {/* main four-point star spark */}
      <path d="M12 2c.45 4.2 1.8 6.9 4.1 8.4 1.2.78 2.7 1.24 4.9 1.6-2.2.36-3.7.82-4.9 1.6C13.8 15.1 12.45 17.8 12 22c-.45-4.2-1.8-6.9-4.1-8.4-1.2-.78-2.7-1.24-4.9-1.6 2.2-.36 3.7-.82 4.9-1.6C10.2 8.9 11.55 6.2 12 2Z" />
      {/* small accent spark */}
      <path d="M19 3c.2 1.5.7 2.4 1.6 2.9.5.3 1.1.5 2 .7-.9.2-1.5.4-2 .7-.9.5-1.4 1.4-1.6 2.9-.2-1.5-.7-2.4-1.6-2.9-.5-.3-1.1-.5-2-.7.9-.2 1.5-.4 2-.7.9-.5 1.4-1.4 1.6-2.9Z" />
    </svg>
  );
}

export default AiGlyph;
