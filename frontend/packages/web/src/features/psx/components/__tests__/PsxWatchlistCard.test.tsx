import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PsxWatchlistCard } from "@/features/psx/components/PsxWatchlistCard";

// The card renders TanStack <Link>s; a plain anchor is enough for these specs.
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, params, ...rest }: Record<string, unknown> & { children?: unknown }) => (
    <a href={String(to)} data-ticker={(params as { ticker?: string })?.ticker} {...rest}>
      {children as React.ReactNode}
    </a>
  ),
}));

const toastFns = vi.hoisted(() => ({ base: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({
  toast: Object.assign(toastFns.base, { success: toastFns.success, error: toastFns.error }),
}));

beforeEach(() => {
  toastFns.base.mockClear();
  toastFns.success.mockClear();
  toastFns.error.mockClear();
});

function renderCard(overrides: Partial<Parameters<typeof PsxWatchlistCard>[0]> = {}) {
  const onRemove = vi.fn();
  render(
    <PsxWatchlistCard
      symbols={["HBL", "ENGRO"]}
      onAdd={vi.fn()}
      onRemove={onRemove}
      addOpen={false}
      onAddOpenChange={vi.fn()}
      snapshot={[{ symbol: "HBL", price: 120, change_pct: 1.2 }]}
      symbolsData={[{ symbol: "HBL", name: "Habib Bank" }]}
      {...overrides}
    />,
  );
  return { onRemove };
}

describe("PsxWatchlistCard remove button", () => {
  it("shows a delete button for every watched symbol", () => {
    renderCard();

    expect(screen.getByRole("button", { name: /remove HBL from watchlist/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /remove ENGRO from watchlist/i }),
    ).toBeInTheDocument();
  });

  it("removes the symbol without navigating to the stock page", async () => {
    const user = userEvent.setup();
    const { onRemove } = renderCard();

    await user.click(screen.getByRole("button", { name: /remove HBL from watchlist/i }));

    expect(onRemove).toHaveBeenCalledExactlyOnceWith("HBL");
  });

  it("does not nest the delete button inside the stock link", () => {
    renderCard();

    const remove = screen.getByRole("button", { name: /remove HBL from watchlist/i });
    expect(remove.closest("a")).toBeNull();
  });

  it("exposes exactly one remove control per row", () => {
    renderCard();

    // The filled star is a state indicator, not a second competing remove.
    expect(screen.getAllByRole("button", { name: /remove HBL/i })).toHaveLength(1);
  });

  it("confirms the removal only after it actually succeeds", async () => {
    const user = userEvent.setup();
    renderCard({ onRemove: vi.fn().mockResolvedValue(undefined) });

    await user.click(screen.getByRole("button", { name: /remove HBL from watchlist/i }));

    expect(toastFns.base).toHaveBeenCalledWith(expect.stringMatching(/HBL.*removed/i));
    expect(toastFns.error).not.toHaveBeenCalled();
  });

  it("reports a failed removal instead of claiming success", async () => {
    const user = userEvent.setup();
    renderCard({ onRemove: vi.fn().mockRejectedValue(new Error("offline")) });

    await user.click(screen.getByRole("button", { name: /remove HBL from watchlist/i }));

    expect(toastFns.error).toHaveBeenCalledWith(expect.stringMatching(/HBL/i));
    expect(toastFns.base).not.toHaveBeenCalledWith(expect.stringMatching(/removed/i));
  });

  it("still links each row through to the stock page", () => {
    renderCard();

    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("data-ticker") === "HBL")).toBe(true);
  });
});
