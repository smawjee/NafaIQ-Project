from __future__ import annotations

from enum import Enum


class SignalLabel(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    NO_SIGNAL = "NO_SIGNAL"


DISPLAY_LABELS: dict[SignalLabel, str] = {
    SignalLabel.STRONG_BUY: "STRONG BUY",
    SignalLabel.BUY: "BUY",
    SignalLabel.HOLD: "HOLD",
    SignalLabel.SELL: "SELL",
    SignalLabel.STRONG_SELL: "STRONG SELL",
    SignalLabel.NO_SIGNAL: "NO SIGNAL",
}

DISPLAY_TO_LABEL: dict[str, SignalLabel] = {v: k for k, v in DISPLAY_LABELS.items()}

_RANK: dict[SignalLabel, int] = {
    SignalLabel.STRONG_SELL: -2,
    SignalLabel.SELL: -1,
    SignalLabel.HOLD: 0,
    SignalLabel.BUY: 1,
    SignalLabel.STRONG_BUY: 2,
    SignalLabel.NO_SIGNAL: -99,
}


def display(label: SignalLabel) -> str:
    return DISPLAY_LABELS[label]


def from_display(value: str | None) -> SignalLabel:
    if not value:
        return SignalLabel.NO_SIGNAL
    normalized = value.upper().replace(" ", "_")
    if normalized in SignalLabel.__members__:
        return SignalLabel[normalized]
    return DISPLAY_TO_LABEL.get(value.upper(), SignalLabel.NO_SIGNAL)


def score_to_signal(score: float) -> SignalLabel:
    if score >= 0.55:
        return SignalLabel.STRONG_BUY
    if score >= 0.15:
        return SignalLabel.BUY
    if score > -0.15:
        return SignalLabel.HOLD
    if score > -0.55:
        return SignalLabel.SELL
    return SignalLabel.STRONG_SELL


def cap_signal(label: SignalLabel, max_label: SignalLabel) -> SignalLabel:
    if label == SignalLabel.NO_SIGNAL or max_label == SignalLabel.NO_SIGNAL:
        return SignalLabel.NO_SIGNAL
    return label if _RANK[label] <= _RANK[max_label] else max_label


def signed_strength(label: SignalLabel) -> float:
    return {
        SignalLabel.STRONG_BUY: 1.0,
        SignalLabel.BUY: 0.55,
        SignalLabel.HOLD: 0.0,
        SignalLabel.SELL: -0.55,
        SignalLabel.STRONG_SELL: -1.0,
        SignalLabel.NO_SIGNAL: 0.0,
    }[label]
