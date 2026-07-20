from __future__ import annotations

from typing import Final

ENGINE_VERSION: Final = "signals-v2"
TECHNICAL_MODEL_VERSION: Final = "technical-v2.0"

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
