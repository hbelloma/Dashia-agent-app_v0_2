"""
test_parser.py
===============
La mitad de estos tests arma un .jsonl a mano para probar casos límite
puntuales. El último (`test_...real_gateway_audit_log`) NO arma nada a
mano — corre binance_connector.gateway.TradingGateway de verdad (con
ccxt mockeado, pero el gateway y su _audit() son el código real) y lee
el archivo que ese gateway escribió solo. Es la prueba que de verdad
importa: que el formato que este parser espera es el que el gateway
realmente produce, no uno inventado para que los tests pasen fácil.
"""
import os
import sys
import json
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stats.parser import read_jsonl, parse_order_style_events, parse_swap_style_events, load_trades
from stats.models import Trade, OpenPosition


def _write_jsonl(tmp_path, name, lines):
    path = str(tmp_path / name)
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return path


def test_read_jsonl_skips_malformed_lines(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_text('{"a": 1}\nesto no es json\n{"b": 2}\n\n')
    events = read_jsonl(str(path))
    assert events == [{"a": 1}, {"b": 2}]


def test_read_jsonl_missing_file_returns_empty_not_a_crash(tmp_path):
    assert read_jsonl(str(tmp_path / "no_existe.jsonl")) == []


def test_pairs_open_and_close_into_a_trade_with_correct_pnl():
    events = [
        {"event": "order", "action": "open_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "qty": 0.1, "price": 60000.0, "ts": "2026-01-01T10:00:00+00:00"},
        {"event": "order", "action": "close_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "price": 61000.0, "ts": "2026-01-01T14:00:00+00:00"},
    ]
    trades, opens = parse_order_style_events(events, "binance")
    assert len(trades) == 1 and opens == []
    t = trades[0]
    assert t.pnl_usd == (61000.0 - 60000.0) * 0.1
    assert t.side == "long"


def test_short_pnl_direction_is_inverted_correctly():
    events = [
        {"event": "order", "action": "open_short", "agent_id": "a1", "symbol": "ETH/USDT",
         "qty": 1.0, "price": 3000.0, "ts": "2026-01-01T10:00:00+00:00"},
        {"event": "order", "action": "close_short", "agent_id": "a1", "symbol": "ETH/USDT",
         "price": 2900.0, "ts": "2026-01-01T12:00:00+00:00"},
    ]
    trades, _ = parse_order_style_events(events, "bybit")
    assert trades[0].pnl_usd == (3000.0 - 2900.0) * 1.0  # short gana cuando el precio baja


def test_unclosed_open_becomes_open_position_not_a_trade():
    events = [
        {"event": "order", "action": "open_long", "agent_id": "a1", "symbol": "SOL/USDT",
         "qty": 5.0, "price": 150.0, "ts": "2026-01-01T10:00:00+00:00"},
    ]
    trades, opens = parse_order_style_events(events, "binance")
    assert trades == []
    assert len(opens) == 1 and opens[0].symbol == "SOL/USDT"


def test_close_without_matching_open_is_ignored_not_invented():
    events = [
        {"event": "order", "action": "close_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "price": 61000.0, "ts": "2026-01-01T10:00:00+00:00"},
    ]
    trades, opens = parse_order_style_events(events, "binance")
    assert trades == [] and opens == []


def test_multiple_trades_same_agent_symbol_pair_fifo():
    events = [
        {"event": "order", "action": "open_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "qty": 0.1, "price": 60000.0, "ts": "2026-01-01T10:00:00+00:00"},
        {"event": "order", "action": "open_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "qty": 0.2, "price": 62000.0, "ts": "2026-01-01T11:00:00+00:00"},
        {"event": "order", "action": "close_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "price": 63000.0, "ts": "2026-01-01T12:00:00+00:00"},
        {"event": "order", "action": "close_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "price": 64000.0, "ts": "2026-01-01T13:00:00+00:00"},
    ]
    trades, opens = parse_order_style_events(events, "binance")
    assert len(trades) == 2 and opens == []
    # FIFO: la primera apertura (qty 0.1 @ 60000) se empareja con el primer cierre (63000)
    assert trades[0].qty == 0.1 and trades[0].entry_price == 60000.0 and trades[0].exit_price == 63000.0
    assert trades[1].qty == 0.2 and trades[1].entry_price == 62000.0 and trades[1].exit_price == 64000.0


def test_solana_pnl_computed_from_usdc_amounts_no_token_decimals_needed():
    events = [
        {"event": "swap", "action": "open_long", "agent_id": "a1", "symbol": "SOL",
         "usdc_in": 100.0, "ts": "2026-01-01T10:00:00+00:00"},
        {"event": "swap", "action": "close_long", "agent_id": "a1", "symbol": "SOL",
         "usdc_out_atomic": 112_500_000, "ts": "2026-01-01T12:00:00+00:00"},  # 112.5 USDC
    ]
    trades, opens = parse_swap_style_events(events)
    assert len(trades) == 1 and opens == []
    t = trades[0]
    assert t.pnl_usd == 12.5
    assert t.qty is None and t.entry_price is None  # a propósito, ver models.py


def test_load_trades_dispatches_by_venue_and_merges(tmp_path):
    binance_path = _write_jsonl(tmp_path, "binance.jsonl", [
        {"event": "order", "action": "open_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "qty": 0.1, "price": 60000.0, "ts": "2026-01-01T10:00:00+00:00"},
        {"event": "order", "action": "close_long", "agent_id": "a1", "symbol": "BTC/USDT",
         "price": 61000.0, "ts": "2026-01-01T11:00:00+00:00"},
    ])
    solana_path = _write_jsonl(tmp_path, "solana.jsonl", [
        {"event": "swap", "action": "open_long", "agent_id": "a1", "symbol": "SOL",
         "usdc_in": 50.0, "ts": "2026-01-01T09:00:00+00:00"},
        {"event": "swap", "action": "close_long", "agent_id": "a1", "symbol": "SOL",
         "usdc_out_atomic": 55_000_000, "ts": "2026-01-01T09:30:00+00:00"},
    ])
    trades, opens = load_trades({"binance": binance_path, "solana": solana_path})
    assert len(trades) == 2
    assert {t.venue for t in trades} == {"binance", "solana"}
    # ordenados por fecha de cierre: el de Solana (09:30) antes que el de Binance (11:00)
    assert trades[0].venue == "solana"


def test_unknown_venue_is_skipped_with_a_warning_not_a_crash(tmp_path):
    weird_path = _write_jsonl(tmp_path, "weird.jsonl", [{"event": "order", "action": "open_long"}])
    trades, opens = load_trades({"coinbase": weird_path})
    assert trades == [] and opens == []


# ---------------------------------------------------------------------------
# La prueba real: log escrito por el gateway de verdad, no armado a mano
# ---------------------------------------------------------------------------
@patch("binance_connector.client.ccxt.binance")
def test_parses_a_real_audit_log_written_by_the_real_gateway(mock_cls, tmp_path):
    from binance_connector.config import BinanceCredentials, GatewayLimits
    from binance_connector.client import BinanceConnector
    from binance_connector.gateway import TradingGateway

    mock_exchange = MagicMock()
    mock_exchange.fetch_ticker.side_effect = [{"last": 60000.0}, {"last": 61500.0}]
    mock_exchange.create_order.return_value = {"id": "order-1"}
    mock_cls.return_value = mock_exchange

    audit_path = str(tmp_path / "real_audit.jsonl")
    conn = BinanceConnector(BinanceCredentials(api_key="x", api_secret="y"), market_type="spot")
    gw = TradingGateway(conn, GatewayLimits(allowed_symbols=("BTC/USDT",)), audit_log_path=audit_path)

    gw.execute_signal("dashia", "open_long", "BTC/USDT", equity_usd=1000)
    gw.execute_signal("dashia", "close_long", "BTC/USDT", equity_usd=1000)

    trades, opens = load_trades({"binance": audit_path})
    assert len(trades) == 1
    assert opens == []
    assert trades[0].pnl_usd > 0  # compró a 60000, vendió a 61500
