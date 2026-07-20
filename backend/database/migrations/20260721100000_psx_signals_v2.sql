-- ================================================================
-- PSX Signals V2: explainable multi-horizon signal cache
-- ================================================================

CREATE TABLE IF NOT EXISTS public.psx_signals_v2 (
    symbol              TEXT NOT NULL,
    horizon             TEXT NOT NULL,
    signal              TEXT NOT NULL,
    confidence          NUMERIC(5,2) NOT NULL,
    rank_score          NUMERIC(5,2) NOT NULL,
    technical_signal    TEXT NOT NULL,
    technical_score     NUMERIC(8,4) NOT NULL,
    ml_signal           TEXT,
    ml_confidence       NUMERIC(5,2),
    risk_level          TEXT NOT NULL,
    regime              TEXT NOT NULL,
    freshness           TEXT NOT NULL,
    reasons             JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings            JSONB NOT NULL DEFAULT '[]'::jsonb,
    indicator_votes     JSONB NOT NULL DEFAULT '[]'::jsonb,
    probabilities       JSONB,
    features_snapshot   JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version       TEXT NOT NULL,
    engine_version      TEXT NOT NULL,
    predicted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, horizon),
    CHECK (horizon IN ('5D', '20D', '60D')),
    CHECK (signal IN ('STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL', 'NO SIGNAL'))
);

CREATE INDEX IF NOT EXISTS idx_psx_signals_v2_signal_confidence
    ON public.psx_signals_v2(signal, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_psx_signals_v2_rank_score
    ON public.psx_signals_v2(rank_score DESC);

CREATE INDEX IF NOT EXISTS idx_psx_signals_v2_predicted
    ON public.psx_signals_v2(predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_psx_signals_v2_symbol
    ON public.psx_signals_v2(symbol);

ALTER TABLE public.psx_signals_v2 ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read psx signals v2"
    ON public.psx_signals_v2
    FOR SELECT
    USING (true);

GRANT SELECT ON public.psx_signals_v2 TO anon, authenticated;
GRANT ALL ON public.psx_signals_v2 TO service_role;
