"""
test_runner.py
===============
market_data y gateway son fakes acá (no tiene sentido levantar un
exchange real para probar el pegamento), pero todo lo que pasa entre
ellos — el DSL corriendo en el sandbox aislado, el cálculo de
indicadores bajo demanda, la derivación de tendencia — es real.
"""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_runtime.runner import run_agent_tick
from agent_sandbox.process_isolation import IsolationLimits


def _trending_ohlcv(direction: str, n=60, start=100.0, step=1.0):
    delta = -step if direction == "down" else step
    close = [start + i * delta for i in range(n)]
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                          "volume": [100.0] * n})


class FakeMarketData:
    def __init__(self, df, fail=False):
        self.df = df
        self.fail = fail
        self.calls = []

    def get_ohlcv(self, symbol, timeframe="1h", limit=300, venue=None):
        self.calls.append((symbol, timeframe, limit, venue))
        if self.fail:
            raise RuntimeError("ningún venue conectado tiene este símbolo")
        return self.df


class FakeGateway:
    def __init__(self):
        self.calls = []

    def execute_signal(self, agent_id, action, symbol, equity_usd):
        self.calls.append((agent_id, action, symbol, equity_usd))
        return {"signature": "fake-ok"}


FAST_LIMITS = IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=8,
                               use_network_namespace=False)


def test_full_tick_buys_on_real_oversold_data():
    md = FakeMarketData(_trending_ohlcv("down"))
    gw = FakeGateway()

    outcome = run_agent_tick(
        "dashia", 'if rsi(14) < 30 and trend == "down":\n    buy(size=risk.default)',
        "BTC/USDT", md, gw, equity_usd=1000, position="none", limits=FAST_LIMITS,
    )

    assert outcome.executed is True
    assert gw.calls == [("dashia", "open_long", "BTC/USDT", 1000)]


def test_trend_variable_is_really_derived_not_hardcoded():
    # Mismo agente, dos series distintas -> el trend calculado debe
    # reflejarlo de verdad, no un valor fijo puesto a mano en algún lado.
    gw = FakeGateway()
    up_outcome = run_agent_tick(
        "a1", 'if trend == "up":\n    buy(size=risk.small)\nif trend == "down":\n    sell(size=risk.small)',
        "BTC/USDT", FakeMarketData(_trending_ohlcv("up")), gw,
        equity_usd=1000, position="none", limits=FAST_LIMITS,
    )
    assert up_outcome.executed is True
    assert gw.calls[-1][1] == "open_long"

    down_outcome = run_agent_tick(
        "a1", 'if trend == "up":\n    buy(size=risk.small)\nif trend == "down":\n    sell(size=risk.small)',
        "BTC/USDT", FakeMarketData(_trending_ohlcv("down")), gw,
        equity_usd=1000, position="none", limits=FAST_LIMITS,
    )
    # sell() estando flat abre un short — comportamiento correcto de
    # _map_action en gateway_bridge.py, no "no hacer nada".
    assert down_outcome.executed is True
    assert gw.calls[-1][1] == "open_short"


def test_market_data_failure_is_reported_without_touching_sandbox_or_gateway():
    md = FakeMarketData(None, fail=True)
    gw = FakeGateway()

    outcome = run_agent_tick(
        "dashia", 'if rsi(14) < 30:\n    buy(size=1)',
        "SOMEWEIRDCOIN", md, gw, equity_usd=1000, limits=FAST_LIMITS,
    )

    assert outcome.executed is False
    assert "sin datos de mercado" in outcome.reason
    assert gw.calls == []


def test_venue_and_timeframe_are_passed_through_to_market_data():
    md = FakeMarketData(_trending_ohlcv("down"))
    run_agent_tick("dashia", "hold()", "ETH/USDT", md, FakeGateway(),
                    equity_usd=500, venue="bybit", timeframe="4h", limit=150, limits=FAST_LIMITS)
    assert md.calls == [("ETH/USDT", "4h", 150, "bybit")]


def test_position_long_allows_closing_via_sell():
    md = FakeMarketData(_trending_ohlcv("up"))  # rsi alto
    gw = FakeGateway()
    outcome = run_agent_tick(
        "dashia", 'if rsi(14) > 70:\n    sell(size=risk.default)',
        "BTC/USDT", md, gw, equity_usd=1000, position="long", limits=FAST_LIMITS,
    )
    assert outcome.executed is True
    assert gw.calls == [("dashia", "close_long", "BTC/USDT", 1000)]


def test_malicious_agent_code_is_still_caught_through_the_full_orchestrator():
    md = FakeMarketData(_trending_ohlcv("down"))
    gw = FakeGateway()
    outcome = run_agent_tick("dashia", "import os\nbuy(size=1)", "BTC/USDT", md, gw, equity_usd=1000, limits=FAST_LIMITS)
    assert outcome.executed is False
    assert "security" in outcome.reason
    assert gw.calls == []
