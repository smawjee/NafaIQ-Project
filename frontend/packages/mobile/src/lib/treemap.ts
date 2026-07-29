// Squarified treemap layout (Bruls, Huizing & van Wijk, 2000), ported for
// react-native absolute-positioned tiles. Pure + deterministic so it can unit
// test. The web app uses d3-hierarchy for the same effect; we keep a tiny
// dependency-free version here since RN has no DOM/SVG treemap primitive.
export interface TreemapTile<T> {
  x: number;
  y: number;
  w: number;
  h: number;
  value: number;
  data: T;
}

interface Scaled<T> {
  area: number;
  value: number;
  data: T;
}

// Worst aspect ratio in a row of the given thickness `len` (the side we tile
// along). Lower is squarer.
function worst<T>(row: Scaled<T>[], len: number): number {
  if (row.length === 0 || len <= 0) return Infinity;
  let sum = 0;
  let max = 0;
  let min = Infinity;
  for (const r of row) {
    sum += r.area;
    if (r.area > max) max = r.area;
    if (r.area < min) min = r.area;
  }
  const len2 = len * len;
  const sum2 = sum * sum;
  return Math.max((len2 * max) / sum2, sum2 / (len2 * min));
}

/**
 * Lay `items` (each with a positive `value`) into a `width`×`height` rect as a
 * squarified treemap. Items should be pre-sorted largest-first for the best
 * (squarest) result. Returns one tile per item; tiles never overlap and fully
 * tile the rect. Non-positive values are dropped.
 */
export function squarify<T>(
  items: { value: number; data: T }[],
  width: number,
  height: number,
): TreemapTile<T>[] {
  const clean = items.filter((it) => it.value > 0);
  const total = clean.reduce((s, it) => s + it.value, 0);
  if (total <= 0 || width <= 0 || height <= 0) return [];

  const scaleFactor = (width * height) / total;
  const remaining: Scaled<T>[] = clean.map((it) => ({
    area: it.value * scaleFactor,
    value: it.value,
    data: it.data,
  }));

  const tiles: TreemapTile<T>[] = [];
  // Free sub-rectangle we are still filling.
  let x = 0;
  let y = 0;
  let w = width;
  let h = height;

  const layoutRow = (row: Scaled<T>[]) => {
    const horizontal = w >= h; // tile stacks along the shorter side
    const len = horizontal ? h : w;
    const sum = row.reduce((s, r) => s + r.area, 0);
    const thickness = len > 0 ? sum / len : 0;
    let pos = horizontal ? y : x;
    for (const r of row) {
      const cell = thickness > 0 ? r.area / thickness : 0;
      if (horizontal) {
        tiles.push({ x, y: pos, w: thickness, h: cell, value: r.value, data: r.data });
      } else {
        tiles.push({ x: pos, y, w: cell, h: thickness, value: r.value, data: r.data });
      }
      pos += cell;
    }
    if (horizontal) {
      x += thickness;
      w -= thickness;
    } else {
      y += thickness;
      h -= thickness;
    }
  };

  let row: Scaled<T>[] = [];
  while (remaining.length > 0) {
    const len = w >= h ? h : w;
    const next = remaining[0];
    if (row.length === 0 || worst([...row, next], len) <= worst(row, len)) {
      row.push(next);
      remaining.shift();
    } else {
      layoutRow(row);
      row = [];
    }
  }
  if (row.length > 0) layoutRow(row);

  return tiles;
}
