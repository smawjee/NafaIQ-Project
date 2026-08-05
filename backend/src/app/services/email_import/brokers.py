"""Versioned broker-confirmation adapters."""
from __future__ import annotations

import hashlib
import io
import re
from datetime import date
from typing import Protocol

from app.services.email_import.broker_models import (
    BrokerConfirmation,
    BrokerParseError,
    BrokerTrade,
)
from app.services.email_import.senders import sender_address

MAX_BROKER_PDF_BYTES = 5 * 1024 * 1024
MAX_BROKER_PDF_PAGES = 10
TOLERANCE = 0.05


class BrokerAdapter(Protocol):
    broker_code: str
    adapter_version: str

    def matches_message(self, sender: str, subject: str, body: str) -> bool: ...

    def parse_pdf(self, data: bytes) -> BrokerConfirmation: ...


def attachment_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def account_fingerprint(account_number: str, user_id: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{account_number}".encode("utf-8")).hexdigest()
    return digest


def sanitize_subject(subject: str) -> str:
    cleaned = re.sub(r"\(\d{4,}\)", "(account)", subject or "")
    cleaned = re.sub(r"\b\d{4,}\b", "#", cleaned)
    return cleaned[:500]


def _money(value: str) -> float:
    return float(value.replace(",", ""))


def _qty(value: str) -> int:
    """Share counts carry thousands separators once they reach four digits.

    JS Global prints `Grand Total : 1,915` exactly as it prints `Grand Total :
    -96`, so a pattern that only accepted bare digits rejected every
    confirmation totalling 1,000 shares or more — the whole note was filed as
    "missing grand total" and every trade on it was lost, including the PRL
    purchase that a later sale then had nothing to sell against.
    """
    return int(value.replace(",", ""))


def _parse_js_date(value: str) -> date:
    if "/" in value:
        day, month, year = value.split("/")
        return date(int(year), int(month), int(day))
    day, month, year = value.split("-")
    full_year = 2000 + int(year) if len(year) == 2 else int(year)
    return date(full_year, int(month), int(day))


def _extract_pdf_text(data: bytes) -> tuple[str, int]:
    if len(data) > MAX_BROKER_PDF_BYTES:
        raise BrokerParseError("PDF attachment is over the 5 MB broker-import limit")
    if not data.startswith(b"%PDF"):
        raise BrokerParseError("Attachment is not a valid PDF", status="unsupported")
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_BROKER_PDF_PAGES:
                raise BrokerParseError("PDF has more than 10 pages")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text, len(pdf.pages)
    except BrokerParseError:
        raise
    except Exception as exc:
        raise BrokerParseError(f"PDF could not be read: {exc}") from exc


class JsGlobalAdapter:
    broker_code = "js_global"
    broker_name = "JS Global"
    adapter_version = "js_global_v1"

    _row_re = re.compile(
        r"^(?P<contract>\d{6,})\s+Ready\s+(?P<settle>\d{2}-\d{2}-\d{2})\s+"
        r"(?P<symbol>[A-Z0-9.]+)\s+(?P<qty>[\d,]+)\s+(?P<rate>[\d,]+\.\d+)\s+"
        r"(?P<brok_rate>[\d,]+\.\d+)\s+(?P<brok>[\d,]+\.\d+)\s+"
        r"(?P<net_rate>[\d,]+\.\d+)\s+(?P<sst>[\d,]+\.\d+)\s+"
        r"(?P<levies>[\d,]+\.\d+)\s+(?P<net>-?[\d,]+\.\d+)$"
    )
    _grand_re = re.compile(
        r"Grand Total\s*:\s*(?P<qty>-?[\d,]+)\s+(?P<brok>[\d,]+\.\d+)\s+"
        r"(?P<sst>[\d,]+\.\d+)\s+(?P<levies>[\d,]+\.\d+)\s+"
        r"(?P<net>-?[\d,]+\.\d+)",
        re.IGNORECASE,
    )

    def matches_message(self, sender: str, subject: str, body: str) -> bool:
        return (
            sender_address(sender) == "equity.settlement@js.com"
            and "trade confirmation" in f"{subject} {body}".lower()
        )

    def parse_pdf(self, data: bytes) -> BrokerConfirmation:
        text, _page_count = _extract_pdf_text(data)
        return self.parse_text(text)

    def parse_text(self, text: str) -> BrokerConfirmation:
        normalized = re.sub(r"[ \t]+", " ", text)
        if "TRADE CONFIRMATION" not in normalized or "JS GLOBAL" not in normalized.upper():
            raise BrokerParseError("PDF is not a JS Global trade confirmation", status="unsupported")
        if not normalized.strip():
            raise BrokerParseError("PDF contains no extractable text", status="unsupported")

        trade_date_match = re.search(r"Trade Date\s+(\d{2}/\d{2}/\d{4})", normalized)
        account_match = re.search(r"Name\s+\[(?P<account>\d{4,})\]", normalized)
        if not trade_date_match or not account_match:
            raise BrokerParseError("JS Global confirmation is missing account or trade date")

        if re.search(r"Purchase orders as under|Buy orders as under", normalized, re.I):
            side = "buy"
        elif re.search(r"Sale orders as under", normalized, re.I):
            side = "sell"
        else:
            raise BrokerParseError("JS Global confirmation is missing buy/sell heading")

        trades: list[BrokerTrade] = []
        for line in normalized.splitlines():
            line = line.strip()
            match = self._row_re.match(line)
            if not match:
                continue
            qty = _qty(match.group("qty"))
            price = _money(match.group("rate"))
            brok = _money(match.group("brok"))
            sst = _money(match.group("sst"))
            levies = _money(match.group("levies"))
            net = _money(match.group("net"))
            expected_net = round(qty * price + brok + sst + levies, 2)
            if side == "sell":
                expected_net = round(-(qty * price - brok - sst - levies), 2)
            if abs(expected_net - net) > TOLERANCE:
                raise BrokerParseError(
                    f"Row {match.group('contract')} net amount mismatch"
                )
            trades.append(
                BrokerTrade(
                    row_index=len(trades) + 1,
                    contract_number=match.group("contract"),
                    symbol=match.group("symbol").upper(),
                    side=side,
                    quantity=qty,
                    price=price,
                    brokerage_amount=brok,
                    sst_amount=sst,
                    levies_amount=levies,
                    net_amount=net,
                    settlement_date=_parse_js_date(match.group("settle")),
                )
            )

        if not trades:
            raise BrokerParseError("JS Global confirmation has no trade rows")

        grand = self._grand_re.search(normalized)
        if not grand:
            raise BrokerParseError("JS Global confirmation is missing grand total")
        total_qty = sum(t.quantity for t in trades)
        if side == "sell":
            total_qty = -total_qty
        total_fees = round(sum(t.fees for t in trades), 2)
        total_net = round(sum(t.net_amount for t in trades), 2)
        reported_net = _money(grand.group("net"))
        reported_fees = round(
            _money(grand.group("brok")) + _money(grand.group("sst")) + _money(grand.group("levies")),
            2,
        )
        if abs(total_qty - _qty(grand.group("qty"))) > 0:
            raise BrokerParseError("Grand total quantity mismatch")
        if abs(total_fees - reported_fees) > TOLERANCE:
            raise BrokerParseError("Grand total fees mismatch")
        if abs(total_net - reported_net) > TOLERANCE:
            raise BrokerParseError("Grand total net amount mismatch")

        account = account_match.group("account")
        return BrokerConfirmation(
            broker_code=self.broker_code,
            broker_name=self.broker_name,
            adapter_version=self.adapter_version,
            account_number=account,
            account_mask=f"****{account[-4:]}",
            trade_date=_parse_js_date(trade_date_match.group(1)),
            settlement_date=trades[0].settlement_date if trades else None,
            total_quantity=total_qty,
            total_fees=total_fees,
            total_net_amount=reported_net,
            trades=tuple(trades),
        )


ADAPTERS: tuple[BrokerAdapter, ...] = (JsGlobalAdapter(),)


def adapter_for_message(sender: str, subject: str, body: str) -> BrokerAdapter | None:
    for adapter in ADAPTERS:
        if adapter.matches_message(sender, subject, body):
            return adapter
    return None
