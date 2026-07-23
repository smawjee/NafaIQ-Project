export type TechnicalSetupRating =
  | "Strong Bullish"
  | "Bullish"
  | "Neutral"
  | "Bearish"
  | "Strong Bearish";

export interface ApiTechnicalComponent {
  name: string;
  vote: -1 | 0 | 1;
  value: number | null;
  reason: string;
}

export interface ApiTechnicalSetup {
  status: "available" | "unavailable";
  rating: TechnicalSetupRating | null;
  score: number | null;
  bar_date: string | null;
  coverage: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  components: ApiTechnicalComponent[];
  version: string;
  reason_code: string | null;
}

export interface ApiForecastOutlook {
  status: "published" | "shadow" | "abstained" | "stale" | "unavailable";
  direction: "OUTPERFORM" | "UNDERPERFORM" | null;
  horizon_sessions: number;
  event_source: { event_type?: string; title?: string; published_at?: string; source_url?: string } | null;
  p_outperform: number | null;
  expected_excess_net: number | null;
  interval: { lower: number; upper: number } | null;
  issued_at: string | null;
  expires_at: string | null;
  model_version: string | null;
  abstain_reason: string | null;
}

export interface ApiSignalV4 {
  symbol: string;
  as_of: string;
  technical_setup: ApiTechnicalSetup;
  forecast: ApiForecastOutlook;
  data_quality: Record<string, unknown>;
}

export interface BatchSignalsV4Response {
  signals: ApiSignalV4[];
  count: number;
  contract: "signals-v4";
}
