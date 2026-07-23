"""The signals_v4 in-process cache must stay bounded.

Before the fix the TTL was only checked on read, so entries accumulated for
every requested symbol and never released — a monotonic RSS chunk on the
single-process Railway box. _cache_put now caps the dict.
"""
from app.services.signals_v4 import service


def test_cache_stays_bounded(monkeypatch):
    service._cache.clear()
    # Insert far more than the cap; the dict must not grow past it.
    for i in range(service._CACHE_MAX_ENTRIES * 3):
        service._cache_put(f"SYM{i}", {"symbol": f"SYM{i}"})
    assert len(service._cache) <= service._CACHE_MAX_ENTRIES
    service._cache.clear()


def test_recent_entry_survives_eviction():
    service._cache.clear()
    for i in range(service._CACHE_MAX_ENTRIES * 2):
        service._cache_put(f"SYM{i}", {"symbol": f"SYM{i}"})
    # The most recently inserted symbol must still be cached (oldest evicted first).
    last = f"SYM{service._CACHE_MAX_ENTRIES * 2 - 1}"
    assert last in service._cache
    service._cache.clear()
