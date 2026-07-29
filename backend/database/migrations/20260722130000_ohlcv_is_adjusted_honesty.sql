-- Make psx_ohlcv.is_adjusted mean what it says (audit 2026-07-22 §2.4).
--
-- Every one of the 976,039 rows carries is_adjusted = true, adjustment_factor
-- = 1.0 and split_date = NULL. That is the column DEFAULT, not a record of work
-- done: multiplying by 1.0 is a no-op, so every bar asserts "I have been
-- split-adjusted" when none has been. Anything trusting the flag is misled.
--
-- FLAG-ONLY. This migration does NOT touch open/high/low/close/volume. No price
-- is read, written, averaged or deleted — the historical series is untouched, in
-- line with the standing rule on PSX history.
--
-- After this:
--   is_adjusted = false  ->  no adjustment has been applied (the honest state
--                            for every current row)
--   is_adjusted = true   ->  set deliberately by a future adjustment routine,
--                            together with a real adjustment_factor/split_date
--
-- Idempotent: the UPDATE is bounded by a WHERE that no longer matches once run.
--
-- BATCHED. A single UPDATE over 976k rows exceeds Supabase's statement timeout
-- and rolls the whole migration back, so the back-fill runs in id-ranged chunks
-- inside a procedure that commits as it goes. That means this file is NOT
-- atomic by design — it is safe to re-run and will resume where it stopped.

-- 1. Stop minting new lies. A freshly scraped bar is unadjusted by definition;
--    only an adjustment routine may set this true.
ALTER TABLE public.psx_ohlcv ALTER COLUMN is_adjusted SET DEFAULT false;

-- 2. Correct the existing claim, but ONLY where the row proves no adjustment
--    ever happened (factor is exactly 1.0 and no split recorded). A row with a
--    real factor or split_date is left alone — it may be genuine.
--
--    A PROCEDURE (not a function) so it can COMMIT between batches; each chunk
--    is its own short statement, well inside the timeout.
CREATE OR REPLACE PROCEDURE public._fix_is_adjusted_batched()
LANGUAGE plpgsql
AS $$
DECLARE
    lo        bigint := 0;
    hi        bigint;
    step      bigint := 50000;
    corrected bigint := 0;
    n         bigint;
BEGIN
    SELECT max(id) INTO hi FROM public.psx_ohlcv;
    WHILE lo <= hi LOOP
        UPDATE public.psx_ohlcv
        SET is_adjusted = false
        WHERE id >= lo AND id < lo + step
          AND is_adjusted = true
          AND adjustment_factor = 1.0
          AND split_date IS NULL;
        GET DIAGNOSTICS n = ROW_COUNT;
        corrected := corrected + n;
        COMMIT;
        lo := lo + step;
    END LOOP;
    RAISE NOTICE 'is_adjusted corrected on % rows (prices untouched).', corrected;
END $$;

CALL public._fix_is_adjusted_batched();
DROP PROCEDURE public._fix_is_adjusted_batched();

-- 3. Tripwire: prove no price data was harmed.
DO $$
DECLARE
    n bigint;
BEGIN
    SELECT count(*) INTO n FROM public.psx_ohlcv;
    IF n < 976039 THEN
        RAISE EXCEPTION
            'psx_ohlcv has % rows, below the 2026-07-22 baseline of 976,039 — '
            'historical market data was lost. Roll back.', n;
    END IF;
    RAISE NOTICE 'psx_ohlcv row count intact: %.', n;
END $$;

INSERT INTO public._applied_migrations (filename, applied_at)
VALUES ('20260722130000_ohlcv_is_adjusted_honesty.sql', now())
ON CONFLICT (filename) DO NOTHING;
