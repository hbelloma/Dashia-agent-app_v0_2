"""
test_scheduler_pass.py
========================
Sin sleep ni loop real — run_scheduler_pass() corre una vez y devuelve.
Pero todo lo demás es real: la bóveda, el gateway (con ccxt mockeado),
el registro de agentes, el registro de posiciones.
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from agent_runtime.registry import AgentRegistry
from agent_runtime.positions import PositionStore
from agent_runtime.scheduler import run_scheduler_pass, MarketDataCache
from agent_sandbox.process_isolation import IsolationLimits

FAST_LIMITS = IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=8,
                               use_network_namespace=False)
NOW = datetime.now(timezone.utc)


@pytest.fixture
def vault(tmp_path):
    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    v = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    yield v
    v.close()


@pytest.fixture
def registry(tmp_path):
    r = AgentRegistry(db_path=str(tmp_path / "agents.db"))
    yield r
    r.close()


@pytest.fixture
def positions(tmp_path):
    p = PositionStore(db_path=str(tmp_path / "positions.db"))
    yield p
    p.close()


@patch("binance_connector.client.ccxt.binance")
def test_due_agent_runs_and_updates_last_run_at(mock_cls, vault, registry, positions):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.fetch_ohlcv.return_value = [[1700000000000 + i * 3600000, 100 - i, 100 - i,
                                                100 - i, 100 - i, 10.0] for i in range(40)]
    mock_exchange.create_order.return_value = {"id": "o1"}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user1", "binance", "K", "S")
    vault.mark_permissions_verified("user1", "binance")
    registry.register_agent("a1", "user1", "Agente 1", 'if rsi(14) < 30:\n    buy(size=risk.default)',
                             "BTC/USDT", "binance", 1000.0, interval_minutes=60)

    results = run_scheduler_pass(registry, vault, positions, MarketDataCache(vault), now=NOW, limits=FAST_LIMITS)

    assert "a1" in results
    assert registry.get_agent("a1").last_run_at is not None
    mock_exchange.create_order.assert_called_once()


@patch("binance_connector.client.ccxt.binance")
def test_agent_not_due_yet_is_skipped(mock_cls, vault, registry, positions):
    mock_cls.return_value = MagicMock()
    vault.save_credential("user1", "binance", "K", "S")
    vault.mark_permissions_verified("user1", "binance")
    registry.register_agent("a1", "user1", "Agente 1", "hold()", "BTC/USDT", "binance",
                             1000.0, interval_minutes=60)
    registry.mark_run("a1", NOW - timedelta(minutes=5))  # corrió hace 5 min, el intervalo es 60

    results = run_scheduler_pass(registry, vault, positions, MarketDataCache(vault), now=NOW, limits=FAST_LIMITS)

    assert results == {}
    mock_cls.assert_not_called()  # ni siquiera se intentó tocar el exchange


@patch("binance_connector.client.ccxt.binance")
def test_one_broken_agent_does_not_block_the_others(mock_cls, vault, registry, positions):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.fetch_ohlcv.return_value = [[1700000000000 + i * 3600000, 100 - i, 100 - i,
                                                100 - i, 100 - i, 10.0] for i in range(40)]
    mock_exchange.create_order.return_value = {"id": "o1"}
    mock_cls.return_value = mock_exchange

    vault.save_credential("user1", "binance", "K", "S")
    vault.mark_permissions_verified("user1", "binance")
    # a_roto: usuario sin credencial de bybit conectada -> build_gateway_for_user falla
    registry.register_agent("a_roto", "user1", "Roto", "hold()", "ETH/USDT", "bybit", 1000.0)
    registry.register_agent("a_bien", "user1", "Bien", 'if rsi(14) < 30:\n    buy(size=risk.default)',
                             "BTC/USDT", "binance", 1000.0)

    results = run_scheduler_pass(registry, vault, positions, MarketDataCache(vault), now=NOW, limits=FAST_LIMITS)

    assert results["a_roto"] is None       # falló, pero no reventó la pasada
    assert results["a_bien"] is not None   # el otro agente corrió igual
    assert registry.get_agent("a_roto").last_run_at is not None  # se marcó igual, no queda "atascado"
    mock_exchange.create_order.assert_called_once()  # solo el agente sano llegó a operar


@patch("binance_connector.client.ccxt.binance")
def test_multiple_users_agents_all_processed_in_one_pass(mock_cls, vault, registry, positions):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.fetch_ohlcv.return_value = [[1700000000000 + i * 3600000, 100 - i, 100 - i,
                                                100 - i, 100 - i, 10.0] for i in range(40)]
    mock_exchange.create_order.return_value = {"id": "o1"}
    mock_cls.return_value = mock_exchange

    for user in ("user1", "user2"):
        vault.save_credential(user, "binance", "K", "S")
        vault.mark_permissions_verified(user, "binance")
    registry.register_agent("a_user1", "user1", "A", 'if rsi(14) < 30:\n    buy(size=risk.default)',
                             "BTC/USDT", "binance", 1000.0)
    registry.register_agent("a_user2", "user2", "B", 'if rsi(14) < 30:\n    buy(size=risk.default)',
                             "BTC/USDT", "binance", 500.0)

    results = run_scheduler_pass(registry, vault, positions, MarketDataCache(vault), now=NOW, limits=FAST_LIMITS)

    assert set(results.keys()) == {"a_user1", "a_user2"}
    assert mock_exchange.create_order.call_count == 2


def test_market_data_cache_reuses_within_ttl(vault):
    with patch("binance_connector.client.ccxt.binance") as mock_cls:
        mock_cls.return_value = MagicMock()
        vault.save_credential("user1", "binance", "K", "S")
        vault.mark_permissions_verified("user1", "binance")

        cache = MarketDataCache(vault, ttl_minutes=30)
        md1 = cache.get("user1")
        md2 = cache.get("user1")
        assert md1 is md2  # mismo objeto, no se reconstruyó
        assert mock_cls.call_count == 1  # el conector de Binance solo se instanció una vez


def test_market_data_cache_invalidate_forces_rebuild(vault):
    with patch("binance_connector.client.ccxt.binance") as mock_cls:
        mock_cls.return_value = MagicMock()
        vault.save_credential("user1", "binance", "K", "S")
        vault.mark_permissions_verified("user1", "binance")

        cache = MarketDataCache(vault)
        cache.get("user1")
        cache.invalidate("user1")
        cache.get("user1")
        assert mock_cls.call_count == 2
