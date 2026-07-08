import type { Holding as BaseHolding, Signal } from "@/lib/data";

export type { Signal };
export type Holding = BaseHolding;

export interface PortfolioState {
  holdings: Holding[];
}
