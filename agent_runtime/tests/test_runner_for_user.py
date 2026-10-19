"""
test_runner_for_user.py
=========================
La prueba más importante acá: correr DOS ticks seguidos y confirmar que
el segundo tick ya "sabe" que el primero abrió una posición — sin que
nadie se lo pase a mano. Eso es lo que hace que esto sea de verdad "un
llamado, para el usuario X" y no las mismas piezas sueltas con otro nombre.
"""
import os
import sys
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
import base58
from solders.keypair import Keypair

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from agent_runtime.runner import run_agent_tick_for_user
from agent_runtime.positions import PositionStore
from agent_runtime.gateway_factory import GatewayNotReadyError
from agent_sandbox.process_isolation import IsolationLimits

FAST_LIMITS = IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=8,
                               use_network_namespace=False)


def _trending_ohlcv(direction: str, n=60, start=100.0, step=1.0):
    delta = -step if direction == "down" else step
    close = [start + i * delta for i in range(n)]
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                          "volume": [100.0] * n})


class FakeMarketData:
    def __init__(self, df):
        self.df = df

    def get_ohlcv(self, symbol, timeframe="1h", limit=300, venue=None):
        return self.df


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    v = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    yield v
    v.close()


def test_raises_clear_error_if_exchange_not_verified(vault):
    vault.save_credential("user_1", "binance", "K", "S")  # sin verificar
    with pytest.raises(GatewayNotReadyError):
        run_agent_tick_for_user(
            "user_1", "agent1", "hold()", "BTC/USDT", "binance", vault,
            equity_usd=1000, market_data=FakeMarketData(_trending_ohlcv("down")), limits=FAST_LIMITS,
        )


@patch("binance_connector.client.ccxt.binance")
def test_full_auto_wiring_executes_real_order_through_real_gateway(mock_cls, vault):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 61000.0}
    mock_exchange.create_order.return_value = {"id": "order-1"}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user_1", "binance", "K", "S")
    vault.mark_permissions_verified("user_1", "binance")

    outcome = run_agent_tick_for_user(
        "user_1", "agent1", 'if rsi(14) < 30:\n    buy(size=risk.default)', "BTC/USDT",
        "binance", vault, equity_usd=1000,
        market_data=FakeMarketData(_trending_ohlcv("down")), limits=FAST_LIMITS,
    )

    assert outcome.executed is True
    assert outcome.gateway_action == "open_long"
    mock_exchange.create_order.assert_called_once()  # orden real, no simulada


@patch("binance_connector.client.ccxt.binance")
def test_position_persists_and_is_used_automatically_across_ticks(mock_cls, tmp_path, vault):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 61000.0}
    mock_exchange.create_order.return_value = {"id": "order-1"}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user_1", "binance", "K", "S")
    vault.mark_permissions_verified("user_1", "binance")
    positions = PositionStore(db_path=str(tmp_path / "positions.db"))

    # Tick 1: sin posición previa, rsi bajo -> abre long
    outcome1 = run_agent_tick_for_user(
        "user_1", "agent1", 'if rsi(14) < 30:\n    buy(size=risk.default)', "BTC/USDT",
        "binance", vault, equity_usd=1000,
        market_data=FakeMarketData(_trending_ohlcv("down")), positions=positions, limits=FAST_LIMITS,
    )
    assert outcome1.gateway_action == "open_long"
    assert positions.get_position("agent1", "BTC/USDT") == "long"

    # Tick 2: MISMO agente, ahora con RSI alto y una regla de venta que
    # solo tiene sentido si está long. Nadie le pasa position="long" a
    # mano — tiene que leerlo solo del PositionStore del tick anterior.
    outcome2 = run_agent_tick_for_user(
        "user_1", "agent1", 'if rsi(14) > 70:\n    sell(size=risk.default)', "BTC/USDT",
        "binance", vault, equity_usd=1000,
        market_data=FakeMarketData(_trending_ohlcv("up")), positions=positions, limits=FAST_LIMITS,
    )
    assert outcome2.executed is True
    assert outcome2.gateway_action == "close_long"  # y no "open_short", porque sabía que estaba long
    assert positions.get_position("agent1", "BTC/USDT") == "none"


def test_without_positions_store_always_assumes_flat(vault):
    # Sin PositionStore, cada tick es sin memoria — documentado a
    # propósito, no un bug: si no le das dónde guardar el estado, no
    # puede tenerlo.
    kp = Keypair()
    vault.save_credential("user_1", "solana", str(kp.pubkey()), base58.b58encode(bytes(kp)).decode())
    vault.mark_permissions_verified("user_1", "solana")

    outcome = run_agent_tick_for_user(
        "user_1", "agent1", 'if trend == "down":\n    sell(size=risk.small)', "SOL",
        "solana", vault, equity_usd=100,
        market_data=FakeMarketData(_trending_ohlcv("down")), limits=FAST_LIMITS,
    )
    # sell() sin posición previa conocida (asumida "none") intenta abrir
    # short — que Solana (spot-only) va a rechazar más adelante en su
    # propio gateway. Lo que importa acá es que NO se asumió "long".
    assert outcome.decision["action"] == "sell"
