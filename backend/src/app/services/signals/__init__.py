"""Evidence-gated signals service — the single engine.

Technical setups are deterministic, and forecasts are read only from promoted,
persisted event-model outputs. The engine never fabricates a HOLD to fill a gap:
when the evidence is missing it says so.
"""

from app.services.signals.service import batch_signals, get_signal

__all__ = ["batch_signals", "get_signal"]
