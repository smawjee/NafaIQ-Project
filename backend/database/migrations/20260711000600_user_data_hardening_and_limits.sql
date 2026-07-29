-- ============================================================================
-- User Data Hardening + Plan Limit Enforcement
-- Adds missing relationships/checks for user-owned finance tables and enforces
-- watchlist limits for the direct Supabase client path.
-- ============================================================================

-- ---------- Finance/user tables: relationships and checks ----------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_transactions_user_id_fkey') THEN
        ALTER TABLE public.user_transactions
            ADD CONSTRAINT user_transactions_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_transactions_amount_positive') THEN
        ALTER TABLE public.user_transactions
            ADD CONSTRAINT user_transactions_amount_positive CHECK (amount > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_transactions_type_check') THEN
        ALTER TABLE public.user_transactions
            ADD CONSTRAINT user_transactions_type_check CHECK (transaction_type IN ('income', 'expense'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_transactions_merchant_not_blank') THEN
        ALTER TABLE public.user_transactions
            ADD CONSTRAINT user_transactions_merchant_not_blank CHECK (length(btrim(merchant)) > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_transactions_category_not_blank') THEN
        ALTER TABLE public.user_transactions
            ADD CONSTRAINT user_transactions_category_not_blank CHECK (length(btrim(category)) > 0);
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_user_txns_user_category_date
    ON public.user_transactions(user_id, category, transaction_date DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_goals_user_id_fkey') THEN
        ALTER TABLE public.user_goals
            ADD CONSTRAINT user_goals_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_goals_target_positive') THEN
        ALTER TABLE public.user_goals
            ADD CONSTRAINT user_goals_target_positive CHECK (target > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_goals_saved_valid') THEN
        ALTER TABLE public.user_goals
            ADD CONSTRAINT user_goals_saved_valid CHECK (saved >= 0 AND saved <= target);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_goals_color_check') THEN
        ALTER TABLE public.user_goals
            ADD CONSTRAINT user_goals_color_check CHECK (color IN ('bull', 'warning'));
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_budgets_user_id_fkey') THEN
        ALTER TABLE public.user_budgets
            ADD CONSTRAINT user_budgets_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_budgets_amounts_valid') THEN
        ALTER TABLE public.user_budgets
            ADD CONSTRAINT user_budgets_amounts_valid CHECK (spent >= 0 AND limit_amount >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_budgets_period_check') THEN
        ALTER TABLE public.user_budgets
            ADD CONSTRAINT user_budgets_period_check CHECK (period IN ('weekly', 'monthly', 'quarterly', 'yearly'));
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_budgets_user_category_period
    ON public.user_budgets(user_id, lower(category), period);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_bills_user_id_fkey') THEN
        ALTER TABLE public.user_bills
            ADD CONSTRAINT user_bills_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_bills_amount_positive') THEN
        ALTER TABLE public.user_bills
            ADD CONSTRAINT user_bills_amount_positive CHECK (amount > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_bills_status_check') THEN
        ALTER TABLE public.user_bills
            ADD CONSTRAINT user_bills_status_check CHECK (status IN ('UPCOMING', 'DUE SOON', 'PAID'));
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_user_bills_user_status_due
    ON public.user_bills(user_id, status, due_date);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_settings_user_id_fkey') THEN
        ALTER TABLE public.user_settings
            ADD CONSTRAINT user_settings_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_settings_plan_check') THEN
        ALTER TABLE public.user_settings
            ADD CONSTRAINT user_settings_plan_check CHECK (plan IN ('Free', 'Pro', 'Premium'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_settings_monthly_income_non_negative') THEN
        ALTER TABLE public.user_settings
            ADD CONSTRAINT user_settings_monthly_income_non_negative CHECK (monthly_income IS NULL OR monthly_income >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'price_alerts_price_positive') THEN
        ALTER TABLE public.price_alerts
            ADD CONSTRAINT price_alerts_price_positive CHECK (price > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_watchlist_user_id_fkey') THEN
        ALTER TABLE public.user_watchlist
            ADD CONSTRAINT user_watchlist_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END;
$$;

-- ---------- Direct Supabase watchlist limit enforcement ----------

CREATE OR REPLACE FUNCTION public.enforce_user_watchlist_plan_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    user_plan TEXT;
    max_items INT;
    current_items INT;
BEGIN
    SELECT COALESCE(plan, 'Free')
    INTO user_plan
    FROM public.profiles
    WHERE id = NEW.user_id;

    SELECT COALESCE(max_watchlist, 10)
    INTO max_items
    FROM public.plan_features
    WHERE plan = COALESCE(user_plan, 'Free');

    SELECT COUNT(*)
    INTO current_items
    FROM public.user_watchlist
    WHERE user_id = NEW.user_id
      AND symbol <> NEW.symbol;

    IF current_items >= COALESCE(max_items, 10) THEN
        RAISE EXCEPTION 'Watchlist limit reached for % plan', COALESCE(user_plan, 'Free')
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS enforce_user_watchlist_plan_limit ON public.user_watchlist;
CREATE TRIGGER enforce_user_watchlist_plan_limit
    BEFORE INSERT OR UPDATE ON public.user_watchlist
    FOR EACH ROW EXECUTE FUNCTION public.enforce_user_watchlist_plan_limit();

-- ---------- Prevent client-side self-upgrades ----------

CREATE OR REPLACE FUNCTION public.prevent_profile_plan_self_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF auth.role() = 'authenticated'
       AND NEW.plan IS DISTINCT FROM OLD.plan THEN
        RAISE EXCEPTION 'Plan changes require an authorized server-side billing/admin flow'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS prevent_profile_plan_self_update ON public.profiles;
CREATE TRIGGER prevent_profile_plan_self_update
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.prevent_profile_plan_self_update();
