import asyncio

import pytest

from app.repositories import signals_v3_repo


class _Res:
    def __init__(self, data):
        self.data = data


def test_complete_scoring_run_status_logic(monkeypatch):
    captured = {}

    async def fake_execute(fn):
        captured["called"] = True
        return _Res([])

    monkeypatch.setattr(signals_v3_repo, "async_execute", fake_execute)
    assert asyncio.run(signals_v3_repo.complete_scoring_run("r1", written=10, expected=10)) == "COMPLETE"
    assert asyncio.run(signals_v3_repo.complete_scoring_run("r1", written=9, expected=10)) == "FAILED"
    assert asyncio.run(signals_v3_repo.complete_scoring_run("r1", written=0, expected=0)) == "FAILED"


def test_insert_signals_attaches_run_metadata(monkeypatch):
    seen = {}

    async def fake_execute(fn):
        class _Table:
            def insert(self, payload):
                seen["payload"] = payload
                return self
        class _Client:
            def table(self, name):
                seen["table"] = name
                return _Table()
        fn(_Client())
        return _Res(seen["payload"])

    monkeypatch.setattr(signals_v3_repo, "async_execute", fake_execute)
    rows = [{"symbol": "HBL", "signal": "BUY"}]
    written = asyncio.run(signals_v3_repo.insert_signals(
        "run-1", rows, model_version="ranker-v3.1-20d", feature_version="v3.1"))
    assert written == 1
    assert seen["table"] == "psx_signals_v3_daily"
    row = seen["payload"][0]
    assert row["scoring_run_id"] == "run-1"
    assert row["model_version"] == "ranker-v3.1-20d"
    assert row["feature_version"] == "v3.1"


def test_insert_signals_empty_short_circuits(monkeypatch):
    async def fail_execute(fn):  # must never be called
        raise AssertionError("no DB call expected for empty rows")

    monkeypatch.setattr(signals_v3_repo, "async_execute", fail_execute)
    assert asyncio.run(signals_v3_repo.insert_signals(
        "run-1", [], model_version="m", feature_version="f")) == 0
