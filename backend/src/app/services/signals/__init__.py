"""Signal service: derived market signals (volume spikes, future detectors).

Distinct from ``app.services.market.signals`` (the ML-based BUY/SELL model).
"""
from app.services.signals.volume_spikes import VolumeSpikeDetector  # noqa: F401
