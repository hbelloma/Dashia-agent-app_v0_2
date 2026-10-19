"""aggregator.py"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class StatsSummary:
    total_trades: int = 0
    open_positions: int = 0
    wins: int = 0
    losses: int = 0
    win_rate_pct: float = 0.0
    total_pnl_usd: float = 0.0
    avg_pnl_usd: float = 0.0
    best_trade_pnl_usd: float | None = None
    worst_trade_pnl_usd: float | None = None
    by_agent: dict = field(default_factory=dict)
    by_venue: dict = field(default_factory=dict)


def summarize(trades: list, open_positions: list) -> StatsSummary:
    if not trades:
        return StatsSummary(open_positions=len(open_positions))

    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd <= 0]
    total_pnl = sum(t.pnl_usd for t in trades)

    by_agent: dict = {}
    for t in trades:
        d = by_agent.setdefault(t.agent_id, {"trades": 0, "pnl_usd": 0.0, "wins": 0})
        d["trades"] += 1
        d["pnl_usd"] += t.pnl_usd
        d["wins"] += 1 if t.pnl_usd > 0 else 0
    for d in by_agent.values():
        d["pnl_usd"] = round(d["pnl_usd"], 2)
        d["win_rate_pct"] = round(100 * d["wins"] / d["trades"], 2)

    by_venue: dict = {}
    for t in trades:
        d = by_venue.setdefault(t.venue, {"trades": 0, "pnl_usd": 0.0})
        d["trades"] += 1
        d["pnl_usd"] += t.pnl_usd
    for d in by_venue.values():
        d["pnl_usd"] = round(d["pnl_usd"], 2)

    pnls = [t.pnl_usd for t in trades]
    return StatsSummary(
        total_trades=len(trades), open_positions=len(open_positions),
        wins=len(wins), losses=len(losses),
        win_rate_pct=round(100 * len(wins) / len(trades), 2),
        total_pnl_usd=round(total_pnl, 2), avg_pnl_usd=round(total_pnl / len(trades), 2),
        best_trade_pnl_usd=round(max(pnls), 2), worst_trade_pnl_usd=round(min(pnls), 2),
        by_agent=by_agent, by_venue=by_venue,
    )
