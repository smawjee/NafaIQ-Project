from __future__ import annotations

from typing import Final

ENGINE_VERSION: Final = "signals-v2"
TECHNICAL_MODEL_VERSION: Final = "technical-v3.0"

DEFAULT_HORIZON: Final = "20D"
HORIZONS: Final = ("5D", "20D", "60D")

MIN_PARTIAL_HISTORY: Final = 80
MIN_FULL_HISTORY: Final = 252
STALE_SNAPSHOT_SECONDS: Final = 900
# PSX snapshots can be the latest valid market state for several hours after
# close. Treat them as delayed, not unusable, until they are clearly stale.
VERY_STALE_SNAPSHOT_SECONDS: Final = 18 * 3600

TECHNICAL_CONFIDENCE_CAP: Final = 70.0
PARTIAL_HISTORY_CONFIDENCE_CAP: Final = 50.0

LOW_LIQUIDITY_SCORE: Final = 25.0
EXTREME_VOLATILITY_SCORE: Final = 85.0

# --- Signals V3.1 ---
MAX_FEATURE_LOOKBACK: Final = 240
FEATURE_SAFETY_BARS: Final = 20
MIN_REQUIRED_BARS: Final = MAX_FEATURE_LOOKBACK + FEATURE_SAFETY_BARS  # 260

ONE_WAY_COST: Final = 0.0025
ROUND_TRIP_COST: Final = 2 * ONE_WAY_COST  # 0.005

TRAINING_GRID_STRIDE: Final = {"5D": 5, "20D": 10, "60D": 20}       # dataset sampling cadence
PORTFOLIO_REBALANCE_DAYS: Final = {"5D": 1, "20D": 5, "60D": 10}    # user-facing portfolio cadence
MAX_ENTRY_DELAY_TRADING_DAYS: Final = 2                             # T+1 entry-failure window
RANK_STALENESS_DAYS: Final = 10                                     # daily-threshold staleness
