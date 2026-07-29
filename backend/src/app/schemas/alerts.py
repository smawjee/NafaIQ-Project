"""Alerts schemas: app-level alert rules and stock price alerts."""
from __future__ import annotations

from typing import Any, Literal, Optional, get_args

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Price-alert conditions — ONE definition, imported everywhere.
#
# This used to be spelled out three times: a regex in PriceAlertCreate, a tuple
# in services/alerts/price_alerts.py, and a Literal in the assistant's
# AddPriceAlertArgs. Three copies of a contract drift, and the drift is silent —
# the DB CHECK constraint is a fourth copy that only fails at INSERT time. The
# single source lives here because a schema IS the contract; the DB constraint
# is kept in step by migration 20260730090000.
# ---------------------------------------------------------------------------

PriceCondition = Literal[
    # Threshold in PKR.
    "above",
    "below",
    "cross_above",
    "cross_below",
    # Threshold is a PERCENT day move (e.g. 5 => +/-5%).
    "pct_change_above",
    "pct_change_below",
    # Threshold is a MULTIPLE of average volume (e.g. 3 => 3x).
    "volume_spike",
    # No threshold — the extreme itself is the condition.
    "high_52w",
    "low_52w",
]

PRICE_CONDITIONS: tuple[str, ...] = get_args(PriceCondition)

#: Conditions whose `price` field carries no meaning. The API accepts a value
#: (0 by default) rather than making the field optional, so the column stays
#: NOT NULL, but nothing should read or display it for these.
THRESHOLDLESS_CONDITIONS: frozenset[str] = frozenset({"high_52w", "low_52w"})

#: What the threshold MEANS per condition — used for validation here and for the
#: unit label the UI renders next to the input.
CONDITION_UNITS: dict[str, str] = {
    "above": "PKR",
    "below": "PKR",
    "cross_above": "PKR",
    "cross_below": "PKR",
    "pct_change_above": "%",
    "pct_change_below": "%",
    "volume_spike": "x",
    "high_52w": "",
    "low_52w": "",
}


class AppAlertCreate(BaseModel):
    type: str = Field(..., pattern="^(stock_price|bill|budget|goal)$")
    title: str = Field(..., min_length=1, max_length=200)
    meta: Optional[dict[str, Any]] = None
    enabled: bool = True


class AppAlertToggle(BaseModel):
    enabled: bool


class PriceAlertCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    condition: PriceCondition
    #: Threshold. Its unit depends on `condition` — see CONDITION_UNITS.
    price: float = Field(0, ge=0)
    one_time: bool = True
    notify_push: bool = False
    notify_email: bool = True
    notes: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check_threshold_makes_sense(self) -> "PriceAlertCreate":
        """Reject thresholds that can never fire, or that fire constantly.

        Without this a user can save `volume_spike` at 0.5x — which is true for
        roughly half of all trading days and would notify them every morning —
        or `pct_change_above` at 500%, which never fires. Both look like working
        alerts in the list and are only discovered by their absence or by the
        noise.
        """
        if self.condition in THRESHOLDLESS_CONDITIONS:
            # Nothing to validate; normalise to 0 so stored rows are consistent
            # rather than carrying whatever the client happened to send.
            self.price = 0
            return self

        if self.price <= 0:
            raise ValueError(f"{self.condition} needs a threshold greater than 0")

        if self.condition in ("pct_change_above", "pct_change_below"):
            # PSX has a 10% daily circuit breaker on most scrips, so anything
            # above ~20 is unreachable. Allow headroom for the exceptions.
            if self.price > 100:
                raise ValueError("percent threshold must be <= 100")
        elif self.condition == "volume_spike":
            if self.price < 1.5:
                raise ValueError("volume multiple must be at least 1.5x to be meaningful")

        return self
