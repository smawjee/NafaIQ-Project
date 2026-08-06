"""Broker-confirmation parse models.

These objects are deliberately small and deterministic: broker adapters produce
facts extracted from evidence, while portfolio services decide whether those
facts may mutate holdings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class BrokerTrade:
    row_index: int
    contract_number: str
    symbol: str
    side: str
    quantity: int
    price: float
    brokerage_amount: float
    sst_amount: float
    levies_amount: float
    net_amount: float
    settlement_date: date

    @property
    def fees(self) -> float:
        return round(self.brokerage_amount + self.sst_amount + self.levies_amount, 2)


@dataclass(frozen=True)
class BrokerConfirmation:
    broker_code: str
    broker_name: str
    adapter_version: str
    account_number: str
    account_mask: str
    trade_date: date
    settlement_date: date | None
    total_quantity: int
    total_fees: float
    total_net_amount: float
    trades: tuple[BrokerTrade, ...]
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


class BrokerParseError(Exception):
    def __init__(self, message: str, *, status: str = "validation_failed") -> None:
        super().__init__(message)
        self.status = status
