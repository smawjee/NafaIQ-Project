"""Unit tests for app.services.permissions.

Pure-function tests; no DB or network access required.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import HTTPException

from app.services.permissions import (
    TIER_RANK,
    has_tier,
    normalize_plan,
    require_tier_or_403,
    tier_rank,
)


def test_tier_rank_order():
    assert tier_rank("Free") < tier_rank("Pro") < tier_rank("Premium")


def test_normalize_plan_handles_case_and_invalid():
    assert normalize_plan("free") == "Free"
    assert normalize_plan("PRO") == "Pro"
    assert normalize_plan("premium") == "Premium"
    assert normalize_plan(None) == "Free"
    assert normalize_plan("") == "Free"
    assert normalize_plan("invalid") == "Free"


def test_has_tier():
    assert has_tier("Free", "Free") is True
    assert has_tier("Pro", "Free") is True
    assert has_tier("Premium", "Pro") is True
    assert has_tier("Free", "Pro") is False
    assert has_tier("Pro", "Premium") is False


def test_require_tier_or_403_passes():
    require_tier_or_403("Pro", "Free")  # no raise


def test_require_tier_or_403_raises():
    with pytest.raises(HTTPException) as exc:
        require_tier_or_403("Free", "Pro")
    assert exc.value.status_code == 403


def test_tier_rank_dict_complete():
    assert set(TIER_RANK.keys()) == {"Free", "Pro", "Premium"}
