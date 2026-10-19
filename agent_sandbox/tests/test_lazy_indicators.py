"""
test_lazy_indicators.py
=========================
Nada mockeado acá — se construye un DataFrame real y se compara contra
llamar a dashia_engine.indicators directo, para confirmar que el puente
no introduce ninguna diferencia.
"""
import os
import sys
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_sandbox.lazy_indicators import LazyIndicatorMap
from dashia_engine.indicators import rsi as real_rsi, sma as real_sma, ema as real_ema


def _sample_df(n=60, seed=3):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "open": close, "high": close + 0.5, "low": close - 0.5,
        "close": close, "volume": rng.uniform(100, 200, n),
    })


def test_rsi_matches_dashia_engine_exactly():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    expected = float(real_rsi(df["close"], 14).iloc[-1])
    assert lazy[("rsi", 14)] == pytest.approx(expected)


def test_sma_matches_dashia_engine_exactly():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    expected = float(real_sma(df["close"], 20).iloc[-1])
    assert lazy[("sma", 20)] == pytest.approx(expected)


def test_ema_matches_dashia_engine_exactly():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    expected = float(real_ema(df["close"], 9).iloc[-1])
    assert lazy[("ema", 9)] == pytest.approx(expected)


def test_price_is_latest_close():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    assert lazy["price"] == float(df["close"].iloc[-1])


def test_volume_is_latest_volume():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    assert lazy["volume"] == float(df["volume"].iloc[-1])


def test_any_period_works_without_precomputing_it():
    # Esto es justo lo que el diseño anterior (dict fijo) no podía dar:
    # ningún período raro fue precalculado, y aun así funciona.
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    assert ("rsi", 37) in lazy
    assert isinstance(lazy[("rsi", 37)], float)


def test_insufficient_history_reports_missing_not_a_crash():
    df = _sample_df(n=10)  # muy poca historia
    lazy = LazyIndicatorMap(df)
    assert ("sma", 50) not in lazy
    with pytest.raises(KeyError):
        _ = lazy[("sma", 50)]


def test_unknown_indicator_name_reports_missing():
    lazy = LazyIndicatorMap(_sample_df())
    assert ("macd", 12) not in lazy


def test_caches_after_first_computation():
    df = _sample_df()
    lazy = LazyIndicatorMap(df)
    v1 = lazy[("rsi", 14)]
    df.loc[df.index[-1], "close"] = 999999  # si recalculara, este valor cambiaría el resultado
    v2 = lazy[("rsi", 14)]
    assert v1 == v2


def test_contains_check_does_not_raise_for_bad_key():
    lazy = LazyIndicatorMap(_sample_df())
    assert ("rsi", -5) not in lazy
    assert ("rsi", "catorce") not in lazy
    assert ("rsi", 14.5) not in lazy  # período no entero, mismo criterio que dsl_interpreter._eval
