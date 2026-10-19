"""test_csv_export.py"""
import os
import sys
import csv
import io
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from stats.csv_export import trades_to_csv
from stats.models import Trade

NOW = datetime(2026, 9, 14, 15, 30, tzinfo=timezone.utc)


def _cex_trade():
    return Trade(agent_id="dashia", venue="binance", symbol="BTC/USDT", side="long",
                 opened_at=NOW, closed_at=NOW, qty=0.1, entry_price=60000.0, exit_price=61000.0,
                 notional_usd=6000.0, pnl_usd=100.0)


def _solana_trade():
    return Trade(agent_id="dashia", venue="solana", symbol="SOL", side="long",
                 opened_at=NOW, closed_at=NOW, qty=None, entry_price=None, exit_price=None,
                 notional_usd=100.0, pnl_usd=12.5)


def test_csv_is_valid_and_parseable():
    csv_text = trades_to_csv([_cex_trade()], lang="es")
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert len(rows) == 2  # encabezado + 1 fila
    assert rows[0][0] == "Fecha apertura"


def test_spanish_headers_by_default():
    csv_text = trades_to_csv([_cex_trade()])
    assert "Ganancia/Pérdida (USD)" in csv_text
    assert "Compra (long)" in csv_text


def test_english_headers_when_requested():
    csv_text = trades_to_csv([_cex_trade()], lang="en")
    assert "P&L (USD)" in csv_text
    assert "Long" in csv_text


def test_unknown_lang_falls_back_to_spanish_not_a_crash():
    csv_text = trades_to_csv([_cex_trade()], lang="fr")
    assert "Fecha apertura" in csv_text


def test_solana_trade_shows_na_instead_of_inventing_price_or_qty():
    csv_text = trades_to_csv([_solana_trade()], lang="es")
    rows = list(csv.reader(io.StringIO(csv_text)))
    row = rows[1]
    header = rows[0]
    qty_idx = header.index("Cantidad")
    price_idx = header.index("Precio entrada")
    assert row[qty_idx] == "N/D"
    assert row[price_idx] == "N/D"


def test_pnl_values_are_numeric_and_correct():
    csv_text = trades_to_csv([_cex_trade()], lang="es")
    rows = list(csv.reader(io.StringIO(csv_text)))
    header, row = rows[0], rows[1]
    pnl_idx = header.index("Ganancia/Pérdida (USD)")
    assert float(row[pnl_idx]) == 100.0


def test_empty_trades_still_produces_valid_csv_with_just_headers():
    csv_text = trades_to_csv([], lang="es")
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert len(rows) == 1
