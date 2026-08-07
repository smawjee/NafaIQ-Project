import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import type { Candle } from "@/lib/data";

/**
 * Candle geometry — the shape of the bars, not the formatting.
 *
 * The reported 1D chart drew every bar as a hairline. Part of that was bad
 * data, but the rest was layout: `ComposedChart` carries two `<Bar>` series
 * (volume and the candle), and recharts groups multiple bars in a category
 * SIDE BY SIDE, splitting the band between them. The candle was handed 5px of
 * a 19.45px slot — a third of its width, and close enough to
 * `MIN_CANDLE_BODY_PX` that a denser window collapsed every candle to a
 * hairline regardless of the data.
 *
 * Volume and price are the same column on a financial chart, so the two bars
 * must overlay (`barGap="-100%"`) rather than sit beside each other.
 *
 * jsdom has no layout engine and `ResponsiveContainer` measures 0x0, so the
 * container is mocked to a fixed viewport — without it every shape collapses
 * and there is nothing to measure.
 */
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) => (
      <actual.ResponsiveContainer width={1200} height={440}>
        {children}
      </actual.ResponsiveContainer>
    ),
  };
});

const { CandlestickChart } = await import("@/components/charts/CandlestickChart");

/** `n` five-minute bars, each with a real body and a wick on both sides. */
function session(n: number): Candle[] {
  const open = Date.UTC(2026, 7, 7, 4, 30);
  return Array.from({ length: n }, (_, i) => {
    const base = 586 + Math.sin(i / 4) * 2;
    const close = base + (i % 2 ? 0.4 : -0.4);
    return {
      date: new Date(open + i * 300_000).toISOString(),
      t: open + i * 300_000,
      open: base,
      high: Math.max(base, close) + 0.5,
      low: Math.min(base, close) - 0.5,
      close,
      volume: 500_000 + i * 1000,
    };
  });
}

function geometry(bars: number) {
  const { container } = render(
    <CandlestickChart data={session(bars)} height={440} tf="1D" mas={[]} />,
  );
  const bodies = Array.from(container.querySelectorAll("rect")).filter(
    (r) => r.getAttribute("rx") === "1",
  );
  const wicks = Array.from(container.querySelectorAll("line")).filter(
    (l) => l.getAttribute("x1") === l.getAttribute("x2"),
  );
  const x = bodies.map((b) => Number(b.getAttribute("x")));
  const width = Number(bodies[0]?.getAttribute("width"));
  return {
    count: bodies.length,
    wicks: wicks.length,
    pitch: x[1] - x[0],
    width,
    centre: x[0] + width / 2,
    wickX: Number(wicks[0]?.getAttribute("x1")),
  };
}

describe("candle geometry", () => {
  it("draws one body and one wick per bar", () => {
    const g = geometry(58);
    expect(g.count).toBe(58);
    expect(g.wicks).toBe(58);
  });

  it("gives the candle most of its category band rather than half of it", () => {
    const g = geometry(58);
    // Side-by-side grouping yielded 0.16 of the band. A real candle sits
    // around half, leaving a visible gutter between neighbours.
    expect(g.width / g.pitch).toBeGreaterThan(0.45);
    expect(g.width / g.pitch).toBeLessThan(0.8);
  });

  it("centres the body on its wick", () => {
    const g = geometry(58);
    expect(g.centre).toBeCloseTo(g.wickX, 5);
  });

  it("keeps bodies above the hairline threshold on a dense window", () => {
    // 90 bars is a full PSX session of 5-minute candles. Under the old
    // side-by-side layout this fell below MIN_CANDLE_BODY_PX and every candle
    // rendered as a single line.
    const g = geometry(90);
    expect(g.width).toBeGreaterThan(3);
  });
});
