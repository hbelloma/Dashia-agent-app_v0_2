"""models.py"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    agent_id: str
    venue: str
    symbol: str
    side: str  # "long" | "short"
    opened_at: datetime
    closed_at: datetime
    qty: float | None          # None en Solana (no hay "cantidad de tokens" comparable directo en USD)
    entry_price: float | None  # None en Solana — ver stats/README.md sobre por qué
    exit_price: float | None
    notional_usd: float
    pnl_usd: float

    @property
    def pnl_pct(self) -> float:
        return (self.pnl_usd / self.notional_usd * 100) if self.notional_usd else 0.0


@dataclass
class OpenPosition:
    agent_id: str
    venue: str
    symbol: str
    side: str
    opened_at: datetime
    qty: float | None
    entry_price: float | None
    notional_usd: float
