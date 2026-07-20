import { squarify } from "@/lib/treemap";

const items = (vals: number[]) => vals.map((value, i) => ({ value, data: `s${i}` }));

describe("squarify", () => {
  it("fully tiles the rect with no overlaps", () => {
    const tiles = squarify(items([6, 6, 4, 3, 2, 2, 1]), 300, 200);
    expect(tiles).toHaveLength(7);
    const area = tiles.reduce((s, t) => s + t.w * t.h, 0);
    expect(area).toBeCloseTo(300 * 200, 0);
    for (const t of tiles) {
      expect(t.x).toBeGreaterThanOrEqual(-0.01);
      expect(t.y).toBeGreaterThanOrEqual(-0.01);
      expect(t.x + t.w).toBeLessThanOrEqual(300.1);
      expect(t.y + t.h).toBeLessThanOrEqual(200.1);
    }
    for (let i = 0; i < tiles.length; i++) {
      for (let j = i + 1; j < tiles.length; j++) {
        const a = tiles[i];
        const b = tiles[j];
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        expect(ox > 0.1 && oy > 0.1).toBe(false);
      }
    }
  });

  it("sizes tiles proportionally to value", () => {
    const tiles = squarify(items([8, 2]), 100, 100);
    const big = tiles.find((t) => t.data === "s0")!;
    const small = tiles.find((t) => t.data === "s1")!;
    expect(big.w * big.h).toBeCloseTo(4 * small.w * small.h, 0);
  });

  it("drops non-positive values and guards empty/zero input", () => {
    expect(squarify(items([0, -5]), 100, 100)).toEqual([]);
    expect(squarify(items([1, 2]), 0, 100)).toEqual([]);
    expect(squarify([], 100, 100)).toEqual([]);
    expect(squarify(items([5, 0, 5]), 100, 100)).toHaveLength(2);
  });
});
