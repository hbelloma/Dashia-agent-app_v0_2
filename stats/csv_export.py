"""csv_export.py"""
from __future__ import annotations
import csv
import io

COLUMNS = {
    "es": ["Fecha apertura", "Fecha cierre", "Agente", "Exchange", "Símbolo", "Lado",
           "Cantidad", "Precio entrada", "Precio salida", "Monto (USD)",
           "Ganancia/Pérdida (USD)", "Ganancia/Pérdida (%)"],
    "en": ["Opened at", "Closed at", "Agent", "Exchange", "Symbol", "Side",
           "Quantity", "Entry price", "Exit price", "Notional (USD)",
           "P&L (USD)", "P&L (%)"],
}

SIDE_LABELS = {
    "es": {"long": "Compra (long)", "short": "Venta (short)"},
    "en": {"long": "Long", "short": "Short"},
}

# Para operaciones de Solana no hay cantidad/precio directo (ver
# models.py) — se deja en blanco en vez de inventar un número.
_NA = {"es": "N/D", "en": "N/A"}


def _fmt(value, lang: str):
    return _NA[lang] if value is None else value


def trades_to_csv(trades: list, lang: str = "es") -> str:
    lang = lang if lang in COLUMNS else "es"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COLUMNS[lang])
    for t in trades:
        writer.writerow([
            t.opened_at.strftime("%Y-%m-%d %H:%M"),
            t.closed_at.strftime("%Y-%m-%d %H:%M"),
            t.agent_id, t.venue, t.symbol,
            SIDE_LABELS[lang].get(t.side, t.side),
            _fmt(round(t.qty, 6) if t.qty is not None else None, lang),
            _fmt(round(t.entry_price, 4) if t.entry_price is not None else None, lang),
            _fmt(round(t.exit_price, 4) if t.exit_price is not None else None, lang),
            round(t.notional_usd, 2),
            round(t.pnl_usd, 2),
            round(t.pnl_pct, 2),
        ])
    return buf.getvalue()


def write_csv(trades: list, path: str, lang: str = "es") -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(trades_to_csv(trades, lang))
