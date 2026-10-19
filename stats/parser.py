"""
parser.py
=========
Lee los logs de auditoría que binance_connector.gateway.TradingGateway
(compartido por Binance/Bybit/Weex) y solana_connector.gateway.
SolanaTradingGateway YA escriben — no hay que agregar ningún logging
nuevo del lado de los gateways, esto lee el formato que ya existe.

Los dos formatos son distintos (confirmado leyendo el código fuente de
cada gateway, no adivinado):

  CEX (event="order"):   open trae qty+price, close trae price
                          (la cantidad del cierre se asume igual a la
                          de la apertura — el sistema no soporta cierres
                          parciales hoy, así que esto es correcto, no
                          una simplificación de este lector).
  Solana (event="swap"): open trae usdc_in, close trae usdc_out_atomic
                          (6 decimales) — P&L sale directo en USD sin
                          necesitar saber los decimales del token.

Una operación se reconstruye emparejando la apertura más antigua sin
cerrar con cada cierre, por (agent_id, symbol, lado) — FIFO. Una
apertura sin cierre todavía queda como OpenPosition, no como Trade.
"""

from __future__ import annotations
import json
import logging
from collections import defaultdict, deque
from datetime import datetime

from .models import Trade, OpenPosition

log = logging.getLogger("stats.parser")

CEX_VENUES = {"binance", "bybit", "weex"}


def _parse_ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["ts"])


def read_jsonl(path: str) -> list[dict]:
    """Nunca lanza por una línea corrupta — la ignora y sigue (un log de
    auditoría append-only puede tener una última línea a medio escribir
    si el proceso se cortó ahí)."""
    events = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    log.warning("Línea %d de %s no es JSON válido, se ignora: %s", i, path, e)
    except FileNotFoundError:
        log.info("No existe todavía el log de auditoría %s (sin operaciones aún)", path)
    return events


def parse_order_style_events(events: list[dict], venue: str) -> tuple[list[Trade], list[OpenPosition]]:
    """CEX — Binance/Bybit/Weex, mismo formato porque comparten TradingGateway."""
    open_queues: dict[tuple, deque] = defaultdict(deque)
    trades: list[Trade] = []

    for ev in events:
        if ev.get("event") != "order":
            continue
        action, agent_id, symbol = ev.get("action"), ev.get("agent_id"), ev.get("symbol")

        if action in ("open_long", "open_short"):
            side = "long" if action == "open_long" else "short"
            open_queues[(agent_id, symbol, side)].append(ev)

        elif action in ("close_long", "close_short"):
            side = "long" if action == "close_long" else "short"
            queue = open_queues[(agent_id, symbol, side)]
            if not queue:
                log.warning("Cierre sin apertura conocida para %s/%s/%s — se ignora, no se inventa un trade",
                            agent_id, symbol, side)
                continue
            open_ev = queue.popleft()
            qty = float(open_ev.get("qty") or 0.0)
            entry_price = float(open_ev.get("price") or 0.0)
            exit_price = float(ev.get("price") or 0.0)
            pnl = (exit_price - entry_price) * qty if side == "long" else (entry_price - exit_price) * qty
            trades.append(Trade(
                agent_id=agent_id, venue=venue, symbol=symbol, side=side,
                opened_at=_parse_ts(open_ev), closed_at=_parse_ts(ev),
                qty=qty, entry_price=entry_price, exit_price=exit_price,
                notional_usd=entry_price * qty, pnl_usd=pnl,
            ))

    open_positions = [
        OpenPosition(
            agent_id=agent_id, venue=venue, symbol=symbol, side=side,
            opened_at=_parse_ts(ev), qty=float(ev.get("qty") or 0.0),
            entry_price=float(ev.get("price") or 0.0),
            notional_usd=float(ev.get("qty") or 0.0) * float(ev.get("price") or 0.0),
        )
        for (agent_id, symbol, side), queue in open_queues.items()
        for ev in queue
    ]
    return trades, open_positions


def parse_swap_style_events(events: list[dict], venue: str = "solana") -> tuple[list[Trade], list[OpenPosition]]:
    """Solana — Jupiter es spot-only, así que side siempre es 'long'."""
    open_queues: dict[tuple, deque] = defaultdict(deque)
    trades: list[Trade] = []

    for ev in events:
        if ev.get("event") != "swap":
            continue
        action, agent_id, symbol = ev.get("action"), ev.get("agent_id"), ev.get("symbol")

        if action == "open_long":
            open_queues[(agent_id, symbol)].append(ev)

        elif action == "close_long":
            queue = open_queues[(agent_id, symbol)]
            if not queue:
                log.warning("Cierre sin apertura conocida para %s/%s en Solana — se ignora", agent_id, symbol)
                continue
            open_ev = queue.popleft()
            usdc_in = float(open_ev.get("usdc_in") or 0.0)
            usdc_out_atomic = ev.get("usdc_out_atomic")
            usdc_out = float(usdc_out_atomic) / 1_000_000 if usdc_out_atomic is not None else 0.0
            trades.append(Trade(
                agent_id=agent_id, venue=venue, symbol=symbol, side="long",
                opened_at=_parse_ts(open_ev), closed_at=_parse_ts(ev),
                qty=None, entry_price=None, exit_price=None,
                notional_usd=usdc_in, pnl_usd=usdc_out - usdc_in,
            ))

    open_positions = [
        OpenPosition(
            agent_id=agent_id, venue=venue, symbol=symbol, side="long",
            opened_at=_parse_ts(ev), qty=None, entry_price=None,
            notional_usd=float(ev.get("usdc_in") or 0.0),
        )
        for (agent_id, symbol), queue in open_queues.items()
        for ev in queue
    ]
    return trades, open_positions


def load_trades(audit_paths: dict[str, str]) -> tuple[list[Trade], list[OpenPosition]]:
    """audit_paths: {"binance": "ruta.jsonl", "solana": "otra.jsonl", ...}
    — una entrada por cada gateway que el usuario tenga en uso."""
    all_trades: list[Trade] = []
    all_open: list[OpenPosition] = []
    for venue, path in audit_paths.items():
        events = read_jsonl(path)
        if venue in CEX_VENUES:
            trades, opens = parse_order_style_events(events, venue)
        elif venue == "solana":
            trades, opens = parse_swap_style_events(events, venue)
        else:
            log.warning("Venue desconocido '%s' — se ignora su log de auditoría", venue)
            continue
        all_trades.extend(trades)
        all_open.extend(opens)
    all_trades.sort(key=lambda t: t.closed_at)
    return all_trades, all_open
