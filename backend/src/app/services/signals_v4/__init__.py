"""Evidence-gated Signals V4 service.

V4 is deliberately separate from the legacy V2/V3 implementation. Technical
setups are deterministic and forecasts are read only from promoted, persisted
event-model outputs.
"""

from app.services.signals_v4.service import batch_signals, get_signal

__all__ = ["batch_signals", "get_signal"]
