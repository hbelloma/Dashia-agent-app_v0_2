"""test_trend.py — velas reales, sin mocks."""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_runtime.trend import derive_trend


def _flat_then_move(pct_move: float, n=60):
    close = [100.0] * (n - 1) + [100.0 * (1 + pct_move / 100)]
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": [1.0] * n})


def test_price_well_above_sma_is_up():
    df = _flat_then_move(5.0)  # +5%, muy por encima de la banda muerta de 0.2%
    assert derive_trend(df) == "up"


def test_price_well_below_sma_is_down():
    df = _flat_then_move(-5.0)
    assert derive_trend(df) == "down"


def test_price_within_dead_band_is_flat():
    df = _flat_then_move(0.05)  # dentro del 0.2% de banda muerta
    assert derive_trend(df) == "flat"


def test_price_exactly_on_sma_is_flat():
    df = _flat_then_move(0.0)
    assert derive_trend(df) == "flat"


def test_insufficient_history_defaults_to_flat_not_a_crash():
    df = pd.DataFrame({"open": [100.0] * 10, "high": [100.0] * 10, "low": [100.0] * 10,
                        "close": [100.0] * 10, "volume": [1.0] * 10})
    assert derive_trend(df, period=50) == "flat"


def test_custom_period_is_respected():
    df = _flat_then_move(5.0, n=25)
    assert derive_trend(df, period=20) == "up"
    assert derive_trend(df, period=50) == "flat"  # no hay 50 velas, cae al default seguro
