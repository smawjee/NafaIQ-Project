import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PsxScreenerCard } from "@/features/psx/components/PsxScreenerCard";
import type { PsxScreenRow } from "@/features/psx/psx.utils";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  Link: ({ children, to, params, ...rest }: Record<string, unknown> & { children?: unknown }) => (
    <a href={String(to)} data-ticker={(params as { ticker?: string })?.ticker} {...rest}>
      {children as React.ReactNode}
    </a>
  ),
}));

const ROWS: PsxScreenRow[] = [
  {
    ticker: "HBL",
    sector: "Banks",
    price: 120,
    changePct: 1.5,
    signal: "BUY",
    signalDetails: {
      symbol: "HBL",
      signal: "BUY",
      confidence: 62,
      horizon: "5d",
      engine_version: "v1",
      reasons: ["momentum"],
      warnings: [],
      risk_level: "MODERATE",
      regime: "NEUTRAL",
      freshness: "LIVE",
      indicator_votes: [],
    } as unknown as PsxScreenRow["signalDetails"],
    rsi: 55,
    volume: "1.2M",
    marketCap: "300B",
  },
  {
    ticker: "ENGRO",
    sector: "Fertilizer",
    price: 280,
    changePct: -0.8,
    signal: null,
    rsi: null,
    volume: "800K",
    marketCap: "150B",
  },
];

function renderCard() {
  render(
    <PsxScreenerCard
      rows={ROWS}
      screenedCount={2}
      screenerStart={1}
      screenerEnd={2}
      currentPage={1}
      pageCount={1}
      onPrev={vi.fn()}
      onNext={vi.fn()}
      searchFilter=""
      onSearchChange={vi.fn()}
      sectorFilter="All"
      onSectorChange={vi.fn()}
      sectors={["Banks", "Fertilizer"]}
      signalFilter="All"
      onSignalChange={vi.fn()}
    />,
  );
}

/** Sector names also appear in the filter <select>, so scope to the table. */
function cell(text: string) {
  return within(screen.getByRole("table")).getByText(text);
}

describe("PsxScreenerCard row navigation", () => {
  it("navigates to the stock when any cell in the row is clicked", async () => {
    const user = userEvent.setup();
    navigate.mockClear();
    renderCard();

    // The sector cell — not the ticker link — is the whole point of the fix.
    await user.click(cell("Fertilizer"));

    expect(navigate).toHaveBeenCalledExactlyOnceWith({
      to: "/stock/$ticker",
      params: { ticker: "ENGRO" },
    });
  });

  it("navigates for the correct row when a price cell is clicked", async () => {
    const user = userEvent.setup();
    navigate.mockClear();
    renderCard();

    await user.click(cell("Banks"));

    expect(navigate).toHaveBeenCalledExactlyOnceWith({
      to: "/stock/$ticker",
      params: { ticker: "HBL" },
    });
  });

  it("does not navigate when the signal-details popover trigger is clicked", async () => {
    const user = userEvent.setup();
    navigate.mockClear();
    renderCard();

    await user.click(screen.getByRole("button", { name: /HBL signal details/i }));

    expect(navigate).not.toHaveBeenCalled();
  });

  it("keeps every row reachable by keyboard through its ticker link", () => {
    renderCard();

    // Row click is a pointer convenience only. The ticker link in each row is
    // the keyboard/AT path — giving the <tr> its own tabIndex would put two
    // tab stops on every row for the same destination.
    const tickers = screen
      .getAllByRole("link")
      .map((a) => a.getAttribute("data-ticker"))
      .filter(Boolean);
    expect(tickers).toEqual(expect.arrayContaining(["HBL", "ENGRO"]));

    expect(cell("Fertilizer").closest("tr")).not.toHaveAttribute("tabindex");
  });

  it("still renders the ticker as a link", () => {
    renderCard();

    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("data-ticker") === "HBL")).toBe(true);
  });
});
