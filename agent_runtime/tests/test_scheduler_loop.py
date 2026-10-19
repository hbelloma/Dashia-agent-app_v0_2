"""
test_scheduler_loop.py
========================
A diferencia de los otros tests, acá SÍ hay un loop real corriendo (en
un thread aparte) con time real, aunque muy acotado — confirma que el
loop de verdad pasa varias veces y que el stop_event de verdad lo corta,
no que "debería funcionar" por leer el código.
"""
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from credentials_vault.crypto import EnvelopeCipher
from credentials_vault.store import CredentialsVault
from agent_runtime.registry import AgentRegistry
from agent_runtime.positions import PositionStore
from agent_runtime.scheduler import run_scheduler_loop
from agent_sandbox.process_isolation import IsolationLimits

FAST_LIMITS = IsolationLimits(cpu_seconds=2, memory_mb=64, wall_clock_timeout_s=8,
                               use_network_namespace=False)


@patch("binance_connector.client.ccxt.binance")
def test_loop_runs_multiple_passes_and_stops_on_event(mock_cls, tmp_path):
    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.return_value = {"last": 100.0}
    mock_exchange.fetch_ohlcv.return_value = [[1700000000000 + i * 3600000, 100.0 - i, 100.0 - i,
                                                100.0 - i, 100.0 - i, 10.0] for i in range(40)]
    mock_exchange.create_order.return_value = {"id": "o1"}
    mock_cls.return_value = mock_exchange

    cipher = EnvelopeCipher(EnvelopeCipher.generate_master_key())
    vault = CredentialsVault(db_path=str(tmp_path / "vault.db"), cipher=cipher)
    registry = AgentRegistry(db_path=str(tmp_path / "agents.db"))
    positions = PositionStore(db_path=str(tmp_path / "positions.db"))

    vault.save_credential("user1", "binance", "K", "S")
    vault.mark_permissions_verified("user1", "binance")
    # intervalo de 0 minutos: le toca correr en CADA pasada del poll,
    # así en unas pocas pasadas reales se nota si el loop de verdad repite
    registry.register_agent("a1", "user1", "A1", "hold()", "BTC/USDT", "binance", 1000.0,
                             interval_minutes=0)

    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_scheduler_loop,
        kwargs=dict(registry=registry, vault=vault, positions=positions,
                    poll_interval_s=0.1, stop_event=stop_event, limits=FAST_LIMITS),
        daemon=True,
    )
    thread.start()
    time.sleep(0.55)  # deberían caber ~5 pasadas a poll de 0.1s
    stop_event.set()
    thread.join(timeout=5)

    assert not thread.is_alive(), "el loop debería haberse detenido al setear stop_event"
    # hold() nunca opera (a propósito, para no mezclar lógica de trading con
    # esta prueba) — lo que confirma que el loop de verdad iteró varias
    # veces es que pidió velas de mercado más de una vez, no una sola.
    assert mock_exchange.fetch_ohlcv.call_count >= 2, (
        f"se esperaban varias pasadas reales, hubo {mock_exchange.fetch_ohlcv.call_count}"
    )

    vault.close()
    registry.close()
    positions.close()
