# backend/scripts

Operational and one-off scripts, grouped by purpose. Every script is run as a
module from the `backend/` directory so `app.*` imports resolve:

```bash
cd backend && python -m scripts.<group>.<name>
```

## Layout

| Folder | Purpose | Re-run? |
|---|---|---|
| `audit/` | Database audit & schema-integrity checks (read-only). | Yes — anytime |
| `data/` | Data import / seed tools (MUFAP NAV CSV, LearnHub ingest, demo user). | Yes — as needed |
| `portfolio/` | Portfolio integrity tooling (holdings ⇄ transactions reconciliation). | Yes — anytime |
| `signals/` | Signals V2 training / backtest / evaluation pipeline. | Yes — see `backend/docs/signals-v2-handoff.md` |
| `archive/` | Historical **one-off** migration appliers & verifiers, kept for the record. | No — already applied |

## Conventions

- **Read-only by default.** Audit scripts must not write. Anything that mutates
  production says so in its module docstring and guards the write.
- **Migrations are not applied from here.** Schema changes live in
  `backend/database/migrations/` and are applied deliberately; the dated
  `archive/apply_migrations_*.py` scripts are a historical record of past
  applies, not a template for new ones. Each migration records itself in
  `_applied_migrations` (see any file dated 2026-07-22 or later for the footer).
- **Never delete or rewrite historical PSX market data** (`psx_ohlcv`,
  `psx_index_eod`). Correct a bad bar by re-fetching that `(symbol, date)` from
  source and upserting — never by deleting or averaging.

## Top-level scripts

- `run_reports_harness.py` — end-to-end exercise of the AI report surfaces.
- `train_signal_model.py` — legacy signal model trainer (see `signals/` for V2).
